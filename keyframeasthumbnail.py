import itertools
import subprocess

from yt_dlp import YoutubeDL
from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessorError, FFmpegVideoConvertorPP
from yt_dlp.utils import Popen, encodeArgument, replace_extension, shell_quote, variadic

class YoutubeDLKeyframe(YoutubeDL):
    def _write_thumbnails(self, label, info_dict, filename, thumb_filename_base=None):
        # just reserving a thumbnail for a keyframe
        if self.params.get('write_all_thumbnails', False):
            self.to_screen('[info] "write_all_thumbnails" is not implemented yet in this script!!')
            return None
        thumb_filename = replace_extension(filename, 'png', info_dict.get('ext'))
        id = 'keyframe'
        with YoutubeDL({'format': 'bv*'}) as ydl:
            info_dict['thumbnails'] = [{
                'url': ydl.process_video_result(info_dict, False)['url'],
                'filepath': thumb_filename
            }]
        self.to_screen(f'[info] Reserving {label} thumbnail for {id} to: {thumb_filename}')
        return [(
            thumb_filename,
            replace_extension(thumb_filename_base or filename, 'png', info_dict.get('ext')))]

class FFmpegWriteKeyframePP(FFmpegVideoConvertorPP):
    _ACTION = 'writing'

    def __init__(self, downloader=None):
        super().__init__(downloader, 'png')

    @classmethod
    def _options(cls, target_ext):
        yield from super()._options(target_ext)
        yield from ('-frames', '1')

    def run_ffmpeg_multiple_files(self, input_paths, out_path, opts, **kwargs):
        return self.real_run_ffmpeg(
            [(path, ['-skip_frame', 'nokey']) for path in input_paths],
            [(out_path, opts)], **kwargs)

    @FFmpegVideoConvertorPP._restrict_to(images=False)
    def run(self, info):
        info_thumb = info['thumbnails'][0]
        filename, outpath = info_thumb['url'], info_thumb['filepath']
        self.to_screen(f'{self._ACTION.title()} keyframe; Destination: {outpath}')
        self.run_ffmpeg(filename, outpath, self._options('png'))
        return [filename], info

    def real_run_ffmpeg(self, input_path_opts, output_path_opts, *, expected_retcodes=(0,)):
        self.check_version()

        cmd = [self.executable, encodeArgument('-y')]
        # avconv does not have repeat option
        if self.basename == 'ffmpeg':
            cmd += [encodeArgument('-loglevel'), encodeArgument('repeat+info')]

        def make_args(file, args, name, number):
            keys = [f'_{name}{number}', f'_{name}']
            if name == 'o':
                args += ['-movflags', '+faststart']
                if number == 1:
                    keys.append('')
            args += self._configuration_args(self.basename, keys)
            if name == 'i':
                args.append('-i')
            return (
                [encodeArgument(arg) for arg in args]
                + [self._ffmpeg_filename_argument(file)])

        for arg_type, path_opts in (('i', input_path_opts), ('o', output_path_opts)):
            cmd += itertools.chain.from_iterable(
                make_args(path, list(opts), arg_type, i + 1)
                for i, (path, opts) in enumerate(path_opts) if path)

        self.write_debug(f'ffmpeg command line: {shell_quote(cmd)}')
        _, stderr, returncode = Popen.run(
            cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        if returncode not in variadic(expected_retcodes):
            self.write_debug(stderr)
            raise FFmpegPostProcessorError(stderr.strip().splitlines()[-1])
        return stderr

with YoutubeDLKeyframe({  # -vx --embed-thumbnail --ffmpeg-location=..\..\ffmpeg-7.1.1-full_build\bin
    'ffmpeg_location': '..\\..\\ffmpeg-7.1.1-full_build\\bin',
    'format': 'ba/b',
    'outtmpl': {'pl_thumbnail': ''},
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'nopostoverwrites': False,
        'preferredcodec': 'best',
        'preferredquality': '5'
    }, {'already_have_thumbnail': False, 'key': 'EmbedThumbnail'}],
    'verbose': True,
    'writethumbnail': True
}) as ydl:
    ydl.add_post_processor(FFmpegWriteKeyframePP(ydl), 'before_dl')
    ydl.download(['BNjW6L4lrYM'])

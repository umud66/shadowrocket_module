import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from convert import convert_module, proxy_github_url, validate_config, make_readme

PREFIX = 'https://gh-proxy.org/'


class ConvertTests(unittest.TestCase):
    def test_raw_github_script(self):
        url = 'https://raw.githubusercontent.com/u/r/main/script.js'
        self.assertEqual(proxy_github_url(url, PREFIX), PREFIX + url)

    def test_github_blob_is_normalized_to_raw(self):
        url = 'https://github.com/u/r/blob/main/scripts/file.js?raw=1'
        self.assertEqual(proxy_github_url(url, PREFIX), PREFIX + 'https://raw.githubusercontent.com/u/r/main/scripts/file.js?raw=1')

    def test_github_raw_is_normalized(self):
        url = 'https://github.com/u/r/raw/sha/scripts/a.js'
        self.assertEqual(proxy_github_url(url, PREFIX), PREFIX + 'https://raw.githubusercontent.com/u/r/sha/scripts/a.js')

    def test_non_raw_github_page_is_unchanged(self):
        url = 'https://github.com/u/r/issues/1'
        self.assertEqual(proxy_github_url(url, PREFIX), url)

    def test_only_download_fields_are_rewritten(self):
        source = ('#!name=Demo\n'
                  '# script-path=https://raw.githubusercontent.com/a/b/main/comment.js\n'
                  '[URL Rewrite]\n'
                  '^https://raw.githubusercontent.com/abc _ reject\n'
                  '[Script]\n'
                  'test=type=http-response,script-path=https://raw.githubusercontent.com/a/b/main/a.js,argument="{}"\n'
                  'remote=type=http-request,script-path=https://example.com/a.js\n'
                  '[Rule]\n'
                  'RULE-SET,https://github.com/a/b/blob/main/rules.list,DIRECT\n'
                  '[MITM]\n'
                  'hostname = %APPEND% github.com\n')
        out = convert_module(source, PREFIX)
        self.assertIn('script-path=' + PREFIX + 'https://raw.githubusercontent.com/a/b/main/a.js,argument="{}"', out)
        self.assertIn('RULE-SET,' + PREFIX + 'https://raw.githubusercontent.com/a/b/main/rules.list,DIRECT', out)
        self.assertIn('# script-path=https://raw.githubusercontent.com/a/b/main/comment.js', out)
        self.assertIn('^https://raw.githubusercontent.com/abc _ reject', out)
        self.assertIn('script-path=https://example.com/a.js', out)
        self.assertEqual(convert_module(out, PREFIX), out)

    def test_invalid_config_rejected(self):
        config = {'repository': 'u/r', 'branch': 'master', 'proxy_prefix': PREFIX,
                  'modules': [{'name': 'Test', 'source': 'https://example.com/a.module',
                               'filename': '../oops.module'}]}
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_readme_has_both_download_options(self):
        config = {'repository': 'u/r', 'branch': 'master', 'proxy_prefix': PREFIX,
                  'modules': [{'name': 'Test', 'source': 'https://example.com/a.module',
                               'filename': 'a.module'}]}
        out = make_readme(config)
        self.assertIn('https://raw.githubusercontent.com/u/r/master/modules/a.module', out)
        self.assertIn(PREFIX + 'https://raw.githubusercontent.com/u/r/master/modules/a.module', out)


    def test_sgmodule_is_accepted(self):
        config = {'repository': 'u/r', 'branch': 'master', 'proxy_prefix': PREFIX,
                  'modules': [{'name': 'YouTube Enhance',
                               'source': 'https://raw.githubusercontent.com/Maasea/sgmodule/refs/heads/master/YouTube.Enhance.sgmodule',
                               'filename': 'YouTube.Enhance.sgmodule'}]}
        validate_config(config)
        out = make_readme(config)
        self.assertIn('modules/YouTube.Enhance.sgmodule', out)

    def test_sgmodule_scripts_are_proxied_without_changing_arguments(self):
        content = ('#!name=YouTube (Music) Enhance\n'
                   '#!arguments=屏蔽上传按钮:true\n'
                   '[Script]\n'
                   'youtube.response = type=http-response,'
                   'script-path=https://raw.githubusercontent.com/Maasea/sgmodule/master/Script/Youtube/youtube.response.js,'
                   'argument="{\\"captionLang\\":\\"{{{字幕翻译语言}}}\\"}"\n'
                   'youtube.request.init = type=http-request,'
                   'script-path=https://raw.githubusercontent.com/Maasea/sgmodule/master/Script/Youtube/youtube.request.js\n'
                   '[MITM]\n'
                   'hostname = %APPEND% *.googlevideo.com, youtubei.googleapis.com\n')
        converted = convert_module(content, PREFIX)
        self.assertEqual(converted.count('script-path=' + PREFIX), 2)
        self.assertIn('argument="{\\"captionLang\\":\\"{{{字幕翻译语言}}}\\"}"', converted)
        self.assertIn('hostname = %APPEND% *.googlevideo.com, youtubei.googleapis.com', converted)
        self.assertEqual(convert_module(converted, PREFIX), converted)

if __name__ == '__main__':
    unittest.main()

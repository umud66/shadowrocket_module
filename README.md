# Shadowrocket 模块 GitHub 代理转换

通过 GitHub Actions 定时下载上游 `.module`，将 `[Script]` 中的 `script-path` 和 `[Rule]` 中的远程 `RULE-SET` GitHub Raw 地址改写为代理地址。 其他规则、脚本参数、MITM 配置保持不变。

> 此 README 的模块清单由 `scripts/convert.py` 自动生成。 代理由第三方提供，速度及可用性可能变化。

## 模块下载

| 模块 | 原始模块 | 转换后的 Raw | 代理后的 Raw（推荐） |
| --- | --- | --- | --- |
| YouTube 去广告 / 画中画 / 后台播放 | [上游原版](https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/youtube.module) | [直接下载](https://raw.githubusercontent.com/umud66/shadowrocket_module/master/modules/youtube.module) | [代理下载](https://gh-proxy.org/https://raw.githubusercontent.com/umud66/shadowrocket_module/master/modules/youtube.module) |
| AdBlock 广告拦截 | [上游原版](https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/adblock.module) | [直接下载](https://raw.githubusercontent.com/umud66/shadowrocket_module/master/modules/adblock.module) | [代理下载](https://gh-proxy.org/https://raw.githubusercontent.com/umud66/shadowrocket_module/master/modules/adblock.module) |
| Spotify 去播放广告 / 播放限制 | [上游原版](https://raw.githubusercontent.com/akiralereal/shadowrocket-toolkit/main/dist/spotify.module) | [直接下载](https://raw.githubusercontent.com/umud66/shadowrocket_module/master/modules/spotify.module) | [代理下载](https://gh-proxy.org/https://raw.githubusercontent.com/umud66/shadowrocket_module/master/modules/spotify.module) |

## 添加或更新模块

只需编辑 [`config/modules.json`](config/modules.json) 的 `modules` 数组，为每个模块填写 `name`、`source`（原始 HTTPS 模块链接）、`filename`（如 `youtube.module`）。
可按需修改 `proxy_prefix`（HTTPS 代理前缀，末尾保留 `/`）。 保存并推送后，GitHub Actions 会自动生成 `modules/` 下的文件及这份链接清单。

也可以在仓库的 **Actions → Sync Shadowrocket modules → Run workflow** 手动运行。 默认每天同步一次；上游下载失败时任务会报错，不会提交不完整内容。

## 转换规则与注意事项

- 仅处理 `[Script]` 内 `script-path=` 以及 `[Rule]` 内 `RULE-SET,` 的 HTTPS GitHub 资源；支持 `raw.githubusercontent.com`、`gist.githubusercontent.com`、`github.com/owner/repo/blob/...` 和 `/raw/...`。
- 已加代理的链接不会重复代理；非 GitHub URL、注释和 URL Rewrite 正则不会改写。
- 这是**链接改写**，不会把外部 JS 下载、托管到本仓库；脚本执行时仍依赖代理服务。
- Shadowrocket 导入模块后，如涉及 HTTPS 响应改写，请按模块说明开启 HTTPS 解密。
- 使用第三方代理意味着模块和脚本下载会经过该服务；敏感或重要场景建议替换为可信的自建代理。

## 本地运行

要求 Python 3.10+，无第三方依赖：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/convert.py
python3 scripts/convert.py --check
```

# 酷狗签到

纯 Python 实现的 `酷狗概念 VIP` 自动签到工具喵。仓库已移除原有 Node/JS 运行链路，现在只保留标准 Python 项目结构。

程序支持：

- 二维码登录添加账号
- 手机号验证码登录添加账号
- 多账号本地管理
- 每日固定时间签到
- 设置随机秒数波动
- 启动后控制台持续输出下一次执行时间与倒计时

## 免责声明

> [!important]
>
> 1. 本项目仅供学习使用，请尊重版权，请勿利用此项目从事商业行为及非法用途!
> 2. 使用本项目的过程中可能会产生版权数据。对于这些版权数据，本项目不拥有它们的所有权。为了避免侵权，使用者务必在 24小时内清除使用本项目的过程中所产生的版权数据。
> 3. 由于使用本项目产生的包括由于本协议或由于使用或无法使用本项目而引起的任何性质的任何直接、间接、特殊、偶然或结果性损害（包括但不限于因商誉损失、停工、计算机故障或故障引起的损害赔偿，或任何及所有其他商业损害或损失）由使用者负责。
> 4. **禁止在违反当地法律法规的情况下使用本项目。** 对于使用者在明知或不知当地法律法规不允许的情况下使用本项目所造成的任何违法违规行为由使用者承担，本项目不承担由此造成的任何直接、间接、特殊、偶然或结果性责任。
> 5. 音乐平台不易，请尊重版权，支持正版。
> 6. 本项目仅用于对技术可行性的探索及研究，不接受任何商业（包括但不限于广告等）合作及捐赠。
> 7. 如果官方音乐平台觉得本项目不妥，可联系本项目更改或移除。
> 8. 本项目完整源代码来自 [develop202/kgcheckin](https://github.com/develop202/kgcheckin),当前仓库仅针对修改为Py版本

## 环境要求

- Python 3.10+
- 可手动创建虚拟环境，也可直接使用一键启动脚本自动创建 `.venv`

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 启动方式

### 1. 交互式控制台

```powershell
python main.py
```

直接进入控制台菜单，可查看账号、添加/删除账号、设置定时，然后启动守护签到。

### 2. 命令行方式

```powershell
python main.py
python main.py account list
python main.py account add-qr
python main.py account add-phone --phone 13800138000
python main.py account remove --user-id 123456
python main.py schedule show
python main.py schedule set --time 00:01 --jitter-seconds 30
python main.py settings show
python main.py settings set --account-gap-min-seconds 5 --account-gap-max-seconds 15 --vip-ad-gap-min-seconds 25 --vip-ad-gap-max-seconds 35
python main.py run
```

### 3. 一键启动脚本

Windows:

```powershell
start_all.bat
```

Linux/macOS:

```bash
chmod +x start_all.sh
./start_all.sh
```

这两个脚本默认直接启动 `run` 守护模式，并会在首次启动时自动创建 `.venv`。如果当前虚拟环境里缺少依赖，脚本会先尝试补齐，再进入主程序。

当前项目的常驻服务只有这一条 Python 主进程，所以按 `Ctrl+C` 会直接结束全部运行中的服务。

如果需要透传参数，也可以这样用：

```powershell
start_all.bat schedule show
start_all.bat account list
```

```bash
./start_all.sh schedule show
./start_all.sh account list
```

`run` 启动后会立即打印：

- 下一次签到的绝对时间
- 当前倒计时
- 本次计划使用的随机波动秒数

如果当前终端支持热键输入，倒计时界面里还可以直接按 `/` 唤出命令栏。当前版本使用 `prompt_toolkit` 处理命令输入：倒计时通过单行状态更新，不再整块清屏闪烁；按下 `/` 后会在下一行打开 `› /` 输入框，并按“一行一个命令 + 后面说明”的形式展示候选。输入 `/remove`、`/schedule`、`/settings` 时会继续给出对应的二级命令提示。回车执行，`Esc` 取消。常用命令示例：

```text
/add qr
/add 13800138000
/remove 123456
/schedule set time 00:01
/schedule set jitter 30
/settings set account-gap 5 15
/settings set ad-gap 25 35
/run
/quit
```

## 配置与数据

程序首次运行会自动生成本地文件：

- `config/config.toml`：定时配置
- `data/accounts.json`：账号列表
- `data/qrcodes/`：二维码登录时生成的 PNG

默认配置示例：

```toml
timezone = "Asia/Shanghai"

[schedule]
time = "00:01"
jitter_min_seconds = 0
jitter_max_seconds = 0

[execution]
account_gap_min_seconds = 0
account_gap_max_seconds = 0
vip_ad_gap_min_seconds = 30
vip_ad_gap_max_seconds = 30
```

如果仓库目录下存在旧版 `USERINFO` JSON 结构，程序会自动迁移为新的 Python 账号格式。

## 项目结构

```text
src/kugou_signer/
  accounts/    账号管理
  config/      配置与本地存储
  kugou/       请求、签名、加密
  scheduler/   定时与倒计时
  services/    签到流程编排
tests/         单元测试
```

## 致谢
     31 -
     32 -- 感谢 [@MakcRe](https://github.com/MakcRe) 提供 API 源代码
     33 -- 感谢 [@itfw](https://github.com/itfw) 提供二维码显示问题的解决方案
     34 -- 感谢 [@klaas8](https://github.com/klaas8) 提供自动写入secret的方法
     35 -- 感谢 [@develop202](https://github.com/develop202) 提供JS版完整源代码
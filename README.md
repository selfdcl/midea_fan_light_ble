# Midea BLE Fan Light

美的蓝牙风扇灯 Home Assistant 自定义集成。首次扫描添加时保存设备 MAC 和所选 ESPHome
广播桥及设备专属协议基序列；后续通过已验证的 `0x4D11` 厂商广播直接控制，通过设备的 `0x06A8` 广播持续获取
状态，不需要为每次操作建立 GATT 连接。新增同协议设备不需要修改或重新编译 ESPHome。

## 当前功能

- 根据厂商 ID `0x06A8`、广播头 `81 63 01` 和广播内倒序 MAC 自动识别设备。
- 通过 Home Assistant 标准配置流发现并添加多台风扇灯。
- 从 `0x06A8` 状态广播同步主灯、风扇、夜灯、风速、方向、亮度、色温和定时。
- 通过 `0x4D11` 原厂兼容双帧广播控制，不建立 GATT 连接：
  - 主灯开关、1–100% 连续亮度和 2700–6500K 连续色温。
  - 风扇开关、1–6 档风速以及标准风/自然风/自动模式；正反转由独立开关控制。
  - 夜灯开关。
  - 关闭及 1–6 小时定时预设。
- 自然风每分钟随机切换一次 1～6 档，关闭风扇或选择其他模式后立即停止。
- 自动模式根据用户选择的 Home Assistant 温度传感器实时调档，默认阈值为 `22/24/26/28/30°C`。
- 兼容 HassLife：风扇百分比映射六档，模式提供标准风、自然风和自动；不声明方向或左右扫风能力。
- 每次控制后等待真实设备状态广播确认，而不是乐观更新界面。

以上命令和加解码逻辑来自真实设备及原厂 App 抓包验证。目前已收录
`80:22:00:60:73:D1`、`80:22:00:40:83:19`、`80:22:00:91:78:26` 和
`80:22:00:A0:2F:DA` 四台设备的独立协议基序列，添加时会按地址自动选择。其他同协议设备
仍会被动态发现，但首次添加时需要输入从原厂 App 控制抓包中取得的 16 字节 XOR 基序列。

## 前置条件

- Home Assistant `2026.7.0` 或更高版本。
- HACS。
- 至少一个刷入本仓库示例配置的 ESPHome BLE 广播控制桥。

ESPHome 广播桥示例位于
[`examples/midea_bluetooth_proxy.yaml`](examples/midea_bluetooth_proxy.yaml)。复制后填写自己的
Wi-Fi、API 和 OTA secrets，再编译刷入一次即可。它同时保留标准 Bluetooth Proxy，另外
注册 `midea_ble_broadcast` 动作供本集成调用。以后添加风扇灯不需要修改或重刷该配置。

> 从 `v0.1.x` 升级到 `v0.2.x` 时，请先刷入新版示例 YAML，等待 ESPHome 设备重新上线并在
> Home Assistant 注册广播动作，然后再更新并重启本集成。只有一个兼容桥时，旧配置条目会
> 自动绑定；存在多个桥时建议重新添加设备并选择距离合适的桥。

> 从 `v0.3.x` 升级到 `v0.4.x` 必须重新刷入本仓库新版 ESPHome 示例 YAML。新版桥接动作会
> 从 Home Assistant 接收每台设备自己的 `xor_base`；只更新集成而不重刷桥接器时，服务调用
> 会因为动作参数不匹配而失败。

当前版本按能力组织为两个主实体和若干本地辅助实体：

- 灯：开关、亮度、色温。
- 风扇：开关、六档风速、标准风/自然风/自动；反转仅由独立开关控制。
- 夜灯：独立开关。
- 定时：独立整小时滑条；倒计时向上归入整小时档位，避免显示 `2.983333… h`。
- 定时剩余：按设备状态广播显示零填充的 `HH:MM`，例如 `01:05`。

自动模式首次使用前，在“设置 → 设备与服务 → Midea BLE Fan Light → 配置”中选择房间
温度传感器。五个阈值分别表示升到 2～6 档的温度，并且必须严格递增；温度传感器变化后
会立即重新计算档位。手动调速、关闭风扇或选择其他模式会退出自动模式。

HassLife 中只添加“灯”和“风扇”两个主实体即可；夜灯与定时留在 Home Assistant 本地时不会
额外占用云端设备名额。

## 接入米家与小爱同学

本集成负责风扇灯与 Home Assistant 之间的本地通信，不会让设备直接成为原生米家设备。
如果需要在米家“其他平台设备”中显示，或使用小爱同学控制，仍需经过 HassLife、巴法云等
已获小米平台接入资格的云端桥接服务。

需要特别注意，“能被小爱控制”和“原生接入米家”不是同一件事。第三方桥接设备通常依赖
“小米云 → 第三方云 → Home Assistant”，断网时不可用；部分能力也可能只支持语音控制，
不能完整参与米家自动化。

### 方案选择

| 方案 | 适用场景 | 注意事项 |
| --- | --- | --- |
| HassLife | 已经在 Home Assistant 中存在的实体 | 配置最简单；本项目已针对其风扇能力做兼容 |
| [Bemfa Cloud](https://github.com/bemfa/bemfa_cloud_ha) | 将 HA 实体同步到巴法云，再由米家或小爱控制 | 推荐使用私钥登录；支持灯、风扇、开关等类型 |
| [BeHome](https://github.com/bemfa/behome) | 把巴法云中原本存在的设备导入 HA | 方向与 Bemfa Cloud 相反，不用于导出本项目实体 |
| [机智云 GSmart](https://docs.gizwits.com/zh-cn/UserManual/NewDev/VoiceApplicationOpeningTutorial.html)、[CozyLife](https://www.cozylife.app/platform/zh/) | 自研或准备量产的硬件产品 | 接入流程更偏产品化和商业化 |
| 易微联、涂鸦 | 使用其模组、SDK 或生态设备 | 通常只能接入各自平台支持的产品，不是任意 HA 实体桥接器 |
| [小米 IoT / 小爱开放平台](https://developers.xiaoai.mi.com/miot) | 正式量产并希望获得原生体验的产品 | 需要平台准入、审核及相关产品认证 |

点灯科技/Blinker 的个人小爱接入服务已于 2025 年 7 月 1 日下线，不再建议作为新方案。

### 通过巴法云接入

本项目对应的正确数据方向为：

```text
美的 BLE 风扇灯 → Midea BLE Fan Light → Home Assistant
                                      ↓
                              Bemfa Cloud → 巴法云 → 米家/小爱
```

安装与配置步骤：

1. 在 HACS 的“自定义存储库”中添加：

   ```text
   https://github.com/bemfa/bemfa_cloud_ha
   ```

   类别选择“集成”，然后安装 **Bemfa Cloud** 并完整重启 Home Assistant。

2. 打开“设置 → 设备与服务 → 添加集成”，搜索 **Bemfa Cloud**。
3. 推荐选择“私钥”认证，填写巴法云控制台中的用户私钥。
4. 选择本集成提供的实体。默认映射关系为：

   | 本项目实体 | 巴法云类型 | 主题后缀 |
   | --- | --- | --- |
   | 主灯 `light` | 灯泡 | `002` |
   | 风扇 `fan` | 风扇 | `003` |
   | 夜灯 `switch` | 开关 | `006` |

5. 在米家中进入“我的 → 其他平台设备 → 添加 → 巴法”，绑定同一个巴法云账号。

Bemfa Cloud 会订阅云端控制消息并调用对应的 HA 实体，同时把 HA 状态变化更新到巴法云。
修改没有稳定 `unique_id` 的实体 ID 可能产生新的巴法主题；日常改名应优先修改实体显示名称。

### BeHome 与 Bemfa Cloud 的区别

这两个集成可以共存，但不要混淆用途：

```text
BeHome:      巴法云设备 → Home Assistant
Bemfa Cloud: Home Assistant 实体 → 巴法云/米家/小爱
```

如果只想把本项目的主灯和风扇交给小爱控制，只安装 Bemfa Cloud 即可。Bemfa Cloud 会过滤
BeHome 生成的实体，避免再次上传形成控制回环。

#### BeHome 1.2.0 配置向导出现 500

在 Home Assistant 2025.12 及更高版本中，`OptionsFlow.config_entry` 由 HA 自动提供，旧代码
再执行 `self.config_entry = config_entry` 会导致：

```text
无法加载配置向导: 500 Internal Server Error
```

这是 BeHome 1.2.0 的已知兼容问题。优先升级到已修复的 BeHome 版本；如果当时仍无新版，
可临时编辑 `/config/custom_components/behome/config_flow.py`。

将：

```python
def async_get_options_flow(config_entry):
    return BeHomeOptionsFlow(config_entry)
```

改为：

```python
def async_get_options_flow(config_entry):
    return BeHomeOptionsFlow()
```

并删除 `BeHomeOptionsFlow.__init__` 中手动保存配置条目的代码：

```python
self.config_entry = config_entry
```

该构造函数中的 `_sync_mode` 赋值在 BeHome 1.2.0 中没有被使用，可以连同构造函数一起删除。
修改后必须完整重启 Home Assistant。相关背景见
[BeHome Issue #14](https://github.com/bemfa/behome/issues/14) 和
[Home Assistant OptionsFlow 迁移说明](https://developers.home-assistant.io/blog/2024/11/12/options-flow/)。

### 自建同类桥接服务

可以自行开发类似 HassLife 或巴法云的服务。技术上需要用户账号与 OAuth、设备模型、状态
查询与控制接口、状态上报、MQTT/WebSocket 长连接，以及对应的 HA 自定义集成。真正的门槛
是小米侧准入：只有得到智能家居服务合作资格和客户端凭据，服务才可以作为自己的品牌出现
在米家“其他平台设备”列表中。个人自建公网服务不能仅靠普通米家 API 注册任意虚拟设备。

如果只是个人或少量用户使用，建议保留本项目的 BLE 本地控制，另行使用 HassLife 或
Bemfa Cloud 做可替换的云端适配层；准备量产时再考虑小米官方、机智云或 CozyLife。

## 通过 HACS 安装

1. 打开 HACS，进入“集成”。
2. 右上角菜单选择“自定义存储库”。
3. 添加存储库：

   ```text
   https://github.com/selfdcl/midea_fan_light_ble
   ```

   类别选择“集成”。

4. 搜索并下载 **Midea BLE Fan Light**。
5. 重启 Home Assistant。
6. 打开“设置 → 设备与服务”。设备广播被接收到后会自动出现；也可选择“添加集成”，
   搜索 **Midea BLE Fan Light**，再选择已扫描到的设备和广播控制桥。

## 手动安装

将 `custom_components/midea_fan_light_ble` 整个目录复制到 Home Assistant：

```text
/config/custom_components/midea_fan_light_ble
```

然后重启 Home Assistant 并按上面的第 6 步添加设备。

## 当前限制

- 夜灯开启时设备状态为 `mode=05`，因此主灯电源位和夜灯位会同时显示开启。
- 定时设置采用设备原生的整小时预设，运行中的剩余时间按小时显示。
- 标准 Home Assistant/ESPHome Bluetooth Proxy 没有任意厂商广播发送接口，因此必须使用
  本仓库扩展后的桥接 YAML，不能只靠主机蓝牙适配器完成控制。
- 不同批次或型号可能使用不同协议；若无法识别，请提交设备广播和调试日志。
- 协议基序列是按设备区分的，不能仅凭 MAC 可靠推导；未收录设备需要提供一次原厂 App
  的命令帧与释放帧抓包，验证后再写入配置。

## 调试日志

在 Home Assistant 的 `configuration.yaml` 临时加入：

```yaml
logger:
  logs:
    custom_components.midea_fan_light_ble: debug
```

重启后复现问题，并在提交 Issue 时附上相关日志。日志可能包含设备蓝牙地址，公开前请按需脱敏。

## 开发验证

协议测试不依赖 Home Assistant，可直接运行：

```bash
python -m unittest discover -s tests -v
```

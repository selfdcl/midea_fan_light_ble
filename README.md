# Midea BLE Fan Light

美的蓝牙风扇灯 Home Assistant 自定义集成。首次扫描添加时保存设备 MAC 和所选 ESPHome
广播桥；后续通过已验证的 `0x4D11` 厂商广播直接控制，通过设备的 `0x06A8` 广播持续获取
状态，不需要为每次操作建立 GATT 连接。新增同协议设备不需要修改或重新编译 ESPHome。

## 当前功能

- 根据厂商 ID `0x06A8`、广播头 `81 63 01` 和广播内倒序 MAC 自动识别设备。
- 通过 Home Assistant 标准配置流发现并添加多台风扇灯。
- 从 `0x06A8` 状态广播同步主灯、风扇、夜灯、风速、方向、亮度、色温和定时。
- 通过 `0x4D11` 原厂兼容双帧广播控制，不建立 GATT 连接：
  - 主灯开关、1–100% 连续亮度和 2700–6500K 连续色温。
  - 风扇开关、1–6 档风速、正反转以及标准风/自然风模式。
  - 夜灯开关。
  - 关闭及 1–6 小时定时预设。
- 自然风每分钟随机切换一次 1～6 档，关闭风扇或选择标准风后立即停止。
- 兼容 HassLife：风扇百分比映射六档，“左右扫风”映射正反转，模式提供标准风和自然风。
- 每次控制后等待真实设备状态广播确认，而不是乐观更新界面。

以上命令和加解码逻辑来自真实设备及原厂 App 抓包验证。目前测试设备地址为
`80:22:00:60:73:D1`，地址并未写死，其他同协议设备会按广播内容动态发现。

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

`v0.3.0` 将实体精简为两个主实体及两个本地辅助实体：

- 灯：开关、亮度、色温。
- 风扇：开关、六档风速、正反转、标准风/自然风。
- 夜灯：独立开关。
- 定时：独立整小时滑条。

HassLife 中只添加“灯”和“风扇”两个主实体即可；夜灯与定时留在 Home Assistant 本地时不会
额外占用云端设备名额。

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

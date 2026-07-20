# Midea BLE Fan Light

美的蓝牙风扇灯 Home Assistant 自定义集成。ESP32 只运行通用 ESPHome Bluetooth
Proxy；设备发现、添加、状态解析和 GATT 控制均由 Home Assistant 完成，因此更换或新增
同协议设备时无需重新编译 ESPHome 固件。

## 当前功能

- 根据厂商 ID `0x06A8`、广播头 `81 63 01` 和广播内倒序 MAC 自动识别设备。
- 通过 Home Assistant 标准配置流发现并添加多台风扇灯。
- 从状态广播及 `BBB1` 通知同步主灯、风扇和夜灯状态。
- 通过 `BBB0` 的 18 字节原厂兼容帧控制：
  - 主灯：命令 `0x06`
  - 风扇：命令 `0x09`
  - 夜灯：命令 `0x5F`
- 控制时短暂建立 GATT 连接，收到状态确认后断开，让设备恢复状态广播。

以上命令和加解码逻辑来自真实设备及原厂 App 抓包验证。目前测试设备地址为
`80:22:00:60:73:D1`，地址并未写死，其他同协议设备会按广播内容动态发现。

## 前置条件

- Home Assistant `2026.7.0` 或更高版本。
- HACS。
- 至少一个支持主动连接的 Home Assistant 蓝牙适配器或 ESPHome Bluetooth Proxy。

ESPHome Proxy 示例位于
[`examples/midea_bluetooth_proxy.yaml`](examples/midea_bluetooth_proxy.yaml)。复制后填写自己的
Wi-Fi、API 和 OTA secrets，再编译刷入一次即可。以后添加风扇灯不需要修改或重刷该配置。

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
   搜索 **Midea BLE Fan Light**，再选择已扫描到的设备。

## 手动安装

将 `custom_components/midea_fan_light_ble` 整个目录复制到 Home Assistant：

```text
/config/custom_components/midea_fan_light_ble
```

然后重启 Home Assistant 并按上面的第 6 步添加设备。

## 当前限制

- 目前只提供已经由真实设备确认的主灯、风扇和夜灯开关。
- 夜灯开启时设备状态为 `mode=05`，因此主灯电源位和夜灯位会同时显示开启。
- 风速、方向、亮度、色温和定时已完成状态解析，但尚未创建控制实体。
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

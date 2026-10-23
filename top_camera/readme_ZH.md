# 患者姿势与场景就绪检查

[English](readme.md) · [技术流程说明](TECHNICAL_FLOW_ZH.md)

使用固定 USB 摄像头和笔记本电脑，在本地检查床上患者的姿势、短时稳定性及周围可见场景。最终只有 **ready** 和 **not ready** 两种结果；姿势与场景必须同时通过，患者无法可靠识别时为 **not ready**。

## 仓库目录

固定摄像头应用位于 `top_camera/`；仓库根目录保留 `LICENSE`、统一的 `.gitignore` 和其他独立模块。本说明中的应用路径均相对于 `top_camera/`。从仓库根目录运行命令前，先进入应用目录：

```powershell
cd top_camera
```

## 环境与启动

- Windows、Python 3.12、USB 摄像头。
- 在连接摄像头的电脑上使用 Edge 或 Chrome，并允许摄像头权限。
- 本地 Python 依赖及 `models/pose_landmarker_full.task` 模型。

当前电脑已安装环境和模型。双击 `start_demo.bat`，打开 [http://localhost:8000](http://localhost:8000)。

新电脑在项目目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_demo.ps1
.\.venv\Scripts\python.exe app.py
```

安装脚本会下载依赖和 Google 官方 Full Pose Landmarker 模型，来源见 [模型说明](models/README.md)。图像推理在本地完成，不依赖网络；应用代码不会上传照片，MediaPipe 预编译运行库可能尝试连接其使用指标服务。

服务只监听 `127.0.0.1`。可选启动参数：

```powershell
.\.venv\Scripts\python.exe app.py --port 8001 --storage runtime/test_session
```

## 演示操作

1. 固定摄像头，清空床面和周边，保留正常设备。
2. 点击 **Calibrate**，程序采集 5 帧，建立空场景基准。
3. 查看自动识别的**黄色床面框**。第 1、2 点表示头端；头脚反向时点击 **Swap head / foot**。框不准确时点击 **Correct bed outline**，从头端一个角开始沿床面周长点击四角，程序自动区分长短边。
4. 勾选 **Yellow outline and head end are correct**。人工确认房间无人、准备正确后，点击 **Use as baseline**。可用 **Ignore area** 忽略小范围摆动电线，但不能把床设为忽略区；忽略区内物品也无法检测。未确认黄色床框不能启用基准。
5. 参与者仰卧，身体沿床长轴，双臂自然放在躯干两侧，或双臂举过头顶。两臂采用同一种姿势，双腿自然放置并保持稳定，点击 **Check**。
6. 程序在约半秒内采集 3 帧，检查姿势、短时移动及可见背景。**蓝框**表示姿势或可见性问题，**红框**表示场景视觉差异。
7. 调整后点击 **Check again**。

校准预览五分钟后过期。服务重启后必须重新校准，磁盘基准不会自动恢复为有效会话。移动床或摄像头、更换摄像头或分辨率后应重新校准。空床也会输出 not ready，因为当前流程要求患者已就位。

## 检测规则

- 使用 MediaPipe 估计 33 个人体关键点及人体分割区域；以本人肩宽、躯干长度、关节角度及床面坐标判断，不要求轮廓重合，不训练个人模板。
- 容忍自然摆位与轻微旋转。身体相对床长轴约 28 度以内的旋转可被接受，但其他部位仍须处于允许范围。
- 三帧中至少两帧通过且最后一帧通过；容忍一次短暂检测丢失及少量关键点抖动，明显移动仍会拦截。
- 从场景差分中排除人体、紧邻边缘及狭窄的脚部区域，不忽略整张床或人体外接矩形。
- 背景检查补偿曝光和局部缓慢光照，抑制可能的阴影、反光，并在对齐可靠时容忍约 2.5 度内的小幅机位旋转及小幅平移。

## 文件结构

| 路径 | 用途 |
|---|---|
| `app.py` | 本地 HTTP 服务、校准会话、综合判断及记录保存 |
| `bed_detection.py` | 空床轮廓自动识别 |
| `positioning.py` | 姿态模型、床面坐标、姿势规则及人体排除掩码 |
| `calibration.py` | 背景基准、图像对齐、光影补偿及差异框 |
| `web/` | 摄像头采集、网页交互及框线显示 |
| `models/` | 本地人体模型和来源说明 |
| `test_demo.py`、`test_positioning.py` | 接口与算法回归测试 |
| `runtime/` | 运行生成的校准快照和检查记录 |
| `archive/` | 历史代码、参考资料、样例照片与开发输出 |

`.venv/` 是当前电脑的 Python 环境，需要保留；换电脑时通过安装脚本重新建立。

## 本地接口与记录

图片使用 JPEG data URL。`camera` 包含摄像头的 `device_id`、`width`、`height`；床角及检测框采用 `[0,1]` 归一化坐标。

| 方法及路径 | 功能 |
|---|---|
| `GET /api/state` | 返回校准状态、ID 及确认的床角 |
| `POST /api/calibration/capture` | 提交 5 个 `images` 和 `camera`；返回预览、`candidate_id`、建议的 `bed_corners`，无法识别时为 null |
| `POST /api/calibration/confirm` | 提交 `candidate_id`、`empty_room_confirmed: true`、`bed_confirmed: true`、`bed_corners`、`ignored_regions` |
| `POST /api/check` | 提交 3 个 `images`、`camera`、`calibration_id`；返回综合结果及红蓝框 |

检查结果包含 `ready`、`status`、`scene_ready`、`pose_ready`、红框 `anomaly_boxes`、蓝框 `pose_boxes`。单张图片可以用于诊断，但缺少稳定性证据，最终不能 ready。无效输入或校准过期等情况返回 400/409 等 HTTP 错误，不作为有效检查结果。

`runtime/baseline.jpg` 和 `baseline.json` 仅作快照留档。检查照片和 JSON 保存在 `runtime/checks/`，约保留最多 200 次或 250 MiB，超限时清理最旧文件。

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_demo.py test_positioning.py
```

测试覆盖校准及人工确认、相对姿势规则、短时移动、旋转与光影容差、人体掩码、可见物品及综合判断。这些是开发验证，不代表临床准确率评估。

## 使用范围

本程序是固定机位演示，不提供临床 CT 扫描许可，不控制 CT、ACU 或机器人；实际摆位由放射技师按检查方案决定。

单个 RGB 摄像头无法可靠验证全部三维姿势、准确仰卧/俯卧、身体与床面的接触或屏气。应让完整患者及双手进入画面；体型、暗光、反光和遮挡仍可能导致误判。

“异物”表示相对空场景的视觉变化，不识别具体类别。人体遮挡、人体/脚部掩码内的物品无法检查。放宽光影容差会降低小型、灰黑色、低对比物品的灵敏度。三帧只检查拍摄窗口内的短时稳定，不是持续监控。

## 归档

见 [归档索引](archive/README.md)。当前应用不导入或提供归档内容。历史照片复核脚本保留当时的目录假设，不再作为当前运行入口。

# CT 顶置相机患者姿势参考图 v1

设计日期：2026-10-24。范围：成人、常规仰卧 CT 的两种常用手臂摆位。图像仍为设计资产，其手臂相对位置关系已在 `positioning.py` 中实现，并由 `criteria.json` 选择方案；插图像素坐标不作为判定阈值。

## 医学依据与适用范围

1. **常规头部 CT**：AAPM《Adult Routine Head CT Protocols》v2.0（2016）描述仰卧、头先进、尽可能使用头托，并按方案控制头颈角度以减少眼晶状体照射。Newcastle Hospitals 的头部 CT 说明也描述仰卧及头托。双臂沿体侧的依据见 SNM《Procedure Guideline for SPECT/CT Imaging 1.0》（2006）图像采集 E.1.2；该条来自 SPECT/CT，作为手臂摆位的补充依据，不把其余核医学流程推广为所有诊断 CT 的要求。
2. **常规胸腹盆 CT**：AAPM《Adult Routine Chest–Abdomen–Pelvis CT Protocols》v1.0（2014）明确描述仰卧、双臂举过头部。UCSF 的 CT 患者安全说明解释，头顶举臂能减少手臂导致的图像伪影。
3. **例外**：ESER 2020 多发伤指南（表 9）要求结合患者状态决定手臂位置；稳定患者的躯干扫描通常举臂，明显肩区损伤等情况例外。本文不把该多发伤建议扩展成所有患者的统一操作流程。不能举臂、疼痛、损伤、单臂下垂或特殊检查方案，应进入技师评估及专门方案，不自动切换为另一常规参考图。

来源：

- [AAPM 头部 CT（2016）](https://aapm.org/pubs/CTProtocols/documents/AdultRoutineHeadCT.pdf)
- [Newcastle Hospitals 头部 CT](https://www.newcastle-hospitals.nhs.uk/services/radiology/ct-scans/ct-head-scan/)
- [SNM SPECT/CT 指南（2006），E.1.2](https://jnm.snmjournals.org/content/47/7/1227)
- [AAPM 胸腹盆 CT（2014）](https://aapm.org/pubs/CTProtocols/documents/AdultRoutineChestAbdomenPelvisCT.pdf)
- [UCSF CT 患者安全与图像质量](https://radiology.ucsf.edu/patient-care/health-professionals/patient-safety-healthcare-professionals/size-and-weight-considerations-imaging-and-image-guided-interventions/info)
- [ESER 多发伤指南（2020），表 9、10](https://link.springer.com/article/10.1186/s13244-020-00947-7)

这些来源支持姿势原则，没有给出适用于顶置 RGB 相机的通用角度、像素或位移合格阈值。图中的宽度、比例和坐标均为工程示意，不能作为临床阈值。DICOM 的头部协议存储示例明确说明其用途是演示编码，故不将其作为临床摆位规范。

## 两张参考图

| 预设 | 医学目标 | 可见几何关系 | 不应强制的条件 |
|---|---|---|---|
| `arms_at_sides` | 常规头部检查的体侧放臂 | 肘、腕处于各自同侧；手部在同侧髋或大腿附近；不横跨躯干 | 手臂完全伸直、手掌方向固定、双腿绝对伸直、身体轮廓匹配 |
| `arms_overhead` | 常规胸腹盆检查的双臂头顶摆位 | 双侧上臂朝头端；双腕向头端离开肩部；双手处于头顶以远区域；手臂不留在胸腹侧 | 肘关节完全伸直、双手接触、完全镜像对称、必须抓住某个位置 |

两图均以头端向上绘制，这与床头方向一致，不代表所有躯干检查都必须头先进机架。患者实际进床方向应是独立配置。

绿色表示示意的手臂目标区域，蓝色表示相机关注的关键点。头托、腿部及身体轮廓仅解释整体摆位。绿色既不是扫描区域，也不是按绝对坐标判断通过的分割掩码。

## 与 top_camera 的接入设计

1. **先选方案，再检测**：由技师或上游检查方案设置 `expected_arm_mode`；侧放方案只接受侧放，举臂方案只接受举臂。不从观察到的手臂姿势反推应该采用的方案。
2. **床面坐标和身体坐标分开**：床面坐标沿用 `BedReference` 的 u、v，u 是床宽方向，v 从床头指向床尾。身体坐标以肩中点为原点、肩到髋为足端方向，长度按本人肩宽及躯干长度归一化。头、肘、腕高于床面，平面投影只提供近似关系，不能当作精确毫米位置。
3. **观察关系而非描边**：使用 MediaPipe 肩 11/12、肘 13/14、腕 15/16、髋 23/24、膝 25/26、踝 27/28。头部可结合鼻 0、眼 2/5、耳 7/8；单个鼻点不能代表头顶，因此“超过头顶”需要头部区域估计，不能直接把鼻点当边界。不要强制每只手都远离中线，避免误拒绝头顶双手靠拢的患者。
4. **目标与移动参考分开**：方案预设定义期望姿势；技师确认后保存本次患者的个体参考关键点用于后续漂移监测。自然呼吸、体型差异与必要支撑应进入容差设计。需要以真实顶置视频确定容差，本设计不先填虚假的医学角度或位移值。
5. **状态与指导**：内部至少区分 `within_criteria`、`reposition_required`、`not_observable`、`manual_review_required`；前端可继续映射为 Within criteria / Outside criteria。举臂方案发现侧放时才提示举臂；不能完成时提示技师协助，不能反复要求患者完成动作。
6. **观察边界**：顶视相机可提供头部横向偏转和手臂位置线索；不能仅据该图确认仰卧、下颌屈曲角、床面接触、扫描垂直等中心、机架安全间隙或屏气。后者分别由技师、设备或额外传感器确认。膝下支撑不应直接被视为腿部异常。

## 文件与复现

- `arms_at_sides_ZH.svg` / `.png`：体侧放臂参考图，可编辑矢量图及预览。
- `arms_overhead_ZH.svg` / `.png`：头顶举臂参考图，可编辑矢量图及预览。
- `reference_maps_comparison_ZH.png`：两图并列预览。
- `reference_maps.design_ZH.json`：仅保存插图坐标及预设标识，`clinical_thresholds` 明确为 null，不是检测配置。
- `render_reference_maps_ZH.py`：使用 Pillow 与 Windows 微软雅黑字体重新生成上述资产。

后续验收样例应至少覆盖：两种正确姿势、选错方案、单臂下垂、肘部自然弯曲、双手靠拢、体型差异、腿垫、遮挡及无法举臂。当前检测已按方案约束手臂模式，躯干 CT 额外检查双腕是否超过估计头部边界；这些工程规则仍需真实摄像头验证。

默认无语言后缀的文件为英文；`_ZH` 后缀为中文。英文设计说明见 [DESIGN.md](DESIGN.md)。

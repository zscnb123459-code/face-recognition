# FaceVault 人脸保险库

**Private Face Recognition System**

FaceVault 是一个面向个人电脑的本地人脸识别桌面应用。它使用电脑摄像头检测人脸，只对用户明确录入并授权的人员进行识别，并将姓名、人脸特征和识别历史保存在本机 SQLite 数据库中。

> **All face data is processed and stored locally by default.**
> 所有人脸数据默认只在本机处理和保存，不上传到任何服务器。

## 重要说明

FaceVault 是个人本地工具，不是银行级身份认证系统，也不具备活体检测能力。照片、视频或屏幕画面可能欺骗普通 RGB 人脸识别模型，因此不要将本项目用于门禁、支付、账号安全或其他高风险身份验证场景。

本项目也不会根据人脸推断年龄、性别、种族、健康状况、情绪或其他敏感属性。

## 已实现功能

- 摄像头实时预览与人脸检测
- 本地人员录入：姓名 + 五个角度的多张特征样本
- 本地人脸识别和多帧稳定确认
- 每张人脸独立识别与显示
- 显示模型相似度 `Similarity`，不把它描述为身份真实性概率
- Unknown 不自动建档、不自动保存人脸照片
- People 人员管理：添加、修改名称、删除、搜索、查看档案状态
- History 识别历史：查看、筛选、真正清空 SQLite 日志
- Dashboard 数据卡片与系统状态
- 设置：摄像头编号、分辨率、FPS、识别阈值、稳定帧数、主题、数据目录
- Stop Camera、Delete Person、Delete All People、Clear History
- 深色/浅色主题，默认深色专业安全软件风格
- 后台识别线程，Qt 界面不会被模型计算直接阻塞
- 日志只记录运行诊断信息，不写入人脸特征或原始画面
- Windows 便携打包，可复制到 U 盘运行

## 技术栈

- Python 3.11+（推荐 3.11 或 3.12；项目也已在 Python 3.14 环境验证）
- PySide6 / Qt 6：桌面 UI
- OpenCV `opencv-contrib-python`：摄像头、图像处理和模型推理接口
- OpenCV Zoo **YuNet**：轻量人脸检测
- OpenCV Zoo **SFace 2021dec**：人脸特征提取
- NumPy：特征向量运算
- SQLite：本地人员、特征和识别日志
- PyInstaller：Windows 便携目录构建

选择 YuNet + SFace 的原因：

- 模型来自 OpenCV 官方生态，安装相对稳定。
- 不需要 dlib、Visual Studio C++ 编译工具或重量级深度学习框架。
- CPU 可以运行，适合个人电脑和 U 盘部署。
- 不需要把图片上传到第三方识别 API。

## 隐私设计

- 默认不自动开启摄像头。
- 每次启动都会显示摄像头与本地数据隐私提示。
- 摄像头只有在用户点击“开启摄像头”或明确选择“按设置开启”后才会打开。
- 顶部栏和主界面始终明确显示摄像头状态。
- `Stop Camera` 会立即请求停止采集并释放摄像头。
- 关闭程序会释放摄像头和后台工作线程。
- 不实现隐藏摄像头、后台偷拍、绕过系统权限等能力。
- Unknown 人脸只产生一条本地识别事件日志，不保存陌生人人脸图像。
- 人员头像使用姓名缩写生成，不依赖原始照片。
- 数据库只保存人脸特征向量，不长期保存录入时的原始照片。
- 识别历史可以由用户永久清空。
- 人员档案及人脸特征可以由用户永久删除。
- 应用运行时不包含上传人脸到第三方服务器的代码路径。

## 环境要求

- Windows 10/11 64 位
- Python 3.11 或更高版本（源码运行）
- 可用的 USB 摄像头或内置摄像头
- 1080p 摄像头体验更佳
- 首次安装依赖需要网络；制作完成后的便携版运行时不需要网络

## Windows 源码安装

在 PowerShell 中进入项目目录：

```powershell
cd C:\Users\你的用户名\Desktop\人脸识别
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python tools\download_models.py
python tools\verify_install.py
python main.py
```

如果 PowerShell 阻止激活脚本，可以运行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

本项目不会在运行时自动下载模型。模型文件放在：

```text
resources/models/face_detection_yunet_2023mar.onnx
resources/models/face_recognition_sface_2021dec.onnx
```

如果模型不存在或损坏，程序会给出友好错误，不会崩溃。可重新执行：

```powershell
python tools\download_models.py
```

## Windows 摄像头权限

1. 打开 Windows“设置”。
2. 进入“隐私和安全性”或“隐私”中的“相机”。
3. 确认“相机访问”已开启。
4. 确认允许桌面应用访问相机。
5. 关闭可能独占摄像头的会议、直播或相机程序。

FaceVault 不尝试绕过 Windows 相机权限。权限被拒绝时，界面会显示可理解的错误提示。

## 运行数据位置

源码运行时，默认数据目录为项目下的 `FaceVaultData`。便携版运行时，数据目录位于 `FaceVault.exe` 同级的 `FaceVaultData`。

典型内容：

```text
FaceVaultData/
├── FaceVault.db        # 人员、特征、识别历史
└── logs/
    └── facevault.log   # 不含人脸特征的运行日志
```

设置文件位于 `FaceVault.exe` 同级的 `FaceVault.config.json`。

如果程序目录不可写，程序会回退到用户的本地 AppData 目录，并在日志中明确记录。

## 使用流程

### 1. 启动和摄像头授权

启动后先阅读隐私提示，然后选择：

- **保持关闭**：程序保持摄像头关闭。
- **按设置开启摄像头**：表示你主动同意本次使用摄像头。

任何时候都可以点击顶部或 Recognition 页面中的 `Stop Camera`。

### 2. 录入人员

1. 打开 `People`。
2. 点击 `Add Person`。
3. 输入姓名。
4. 点击“开始录入”。
5. 按提示依次完成正面、左转、右转、抬头、低头五个角度。
6. 每个角度调整好位置后点击“采集此角度”。
7. 采集完成后点击“保存本地档案”。

程序只保存 SFace 特征向量和采集质量分数，不保存用于录入的原始照片。录入过程中，图像只存在于内存和摄像头缓冲区中。

### 3. 实时识别

1. 打开 `Recognition`。
2. 点击“开启摄像头”。
3. 每张人脸拥有独立检测框和识别结果。
4. 结果连续多帧一致后，界面才显示 `Recognized` 或 `Unknown`。
5. 修改识别阈值后，需要停止并重新开启摄像头，或者重启程序。

### 4. 人员管理和删除

- `修改名称`：只更新数据库中的姓名，不改变特征。
- `删除人员档案`：需要连续两次确认，并会级联删除该人员全部本地特征。
- `Delete All People`：需要二次确认并输入指定中文确认文字。

删除操作面向真实 SQLite 数据，不是只隐藏 UI 项。

### 5. History

History 记录识别时间、结果、是否匹配、Similarity 和摄像头状态。

`Clear History` 会执行真正的 SQLite `DELETE`，不是仅清空界面列表。清除后无法恢复。

## 识别阈值与相似度

默认阈值集中定义在 `app/config.py`：

```python
DEFAULT_RECOGNITION_THRESHOLD = 0.42
```

也可以在 Settings 页面修改。阈值越高，误识别通常越少，但合法用户更容易显示为 Unknown；阈值越低，更容易匹配，但误识别风险增加。

`Similarity` 是 SFace 特征向量之间的余弦相似度，不是“这个人是某人的真实概率”。实际使用时应用自己的正样本和负样本测试并调整阈值。

## 错误处理

程序已覆盖以下异常场景：

- 没有摄像头
- 摄像头被其他程序占用
- Windows 摄像头权限被拒绝
- 摄像头读取中断
- 模型文件丢失或损坏
- 模型加载或推理失败
- SQLite 数据库破损或无法打开
- 画面中没有人脸
- 画面中存在多张人脸
- 人脸过小、过暗、过亮、模糊或对比度不足

数据库 `quick_check` 失败时，损坏文件会被重命名为 `.corrupt_时间戳`，然后创建新数据库。原文件不会被静默删除。

## 项目结构

```text
人脸识别/
├── main.py
├── launcher.py                 # 中文/ U 盘路径启动器
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── FaceVault.spec              # 主程序构建配置
├── FaceVaultLauncher.spec      # 启动器构建配置
├── build_version_info.txt
├── app/
│   ├── camera.py                 # 摄像头与识别后台线程
│   ├── database.py               # SQLite 参数化数据访问
│   ├── enrollment.py             # 引导式人员录入
│   ├── models.py                 # 数据模型
│   ├── paths.py                  # 源码/便携路径
│   ├── recognition.py            # YuNet + SFace + 稳定机制
│   ├── settings.py               # 设置门面
│   ├── services/
│   │   └── settings_service.py
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── theme.py
│   │   ├── widgets.py
│   │   ├── dialogs/
│   │   └── pages/
│   │       ├── dashboard.py
│   │       ├── people.py
│   │       ├── recognition.py
│   │       ├── history.py
│   │       └── settings.py
│   └── utils/
│       ├── image_utils.py
│       └── logging_setup.py
├── resources/
│   ├── branding/
│   └── models/
├── tools/
│   ├── download_models.py
│   ├── verify_install.py
│   └── build_portable.ps1
└── tests/
```

## 数据库结构

```sql
people (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)

face_embeddings (
    id INTEGER PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    embedding BLOB NOT NULL,
    model_name TEXT NOT NULL,
    quality REAL NOT NULL,
    created_at TEXT NOT NULL
)

recognition_history (
    id INTEGER PRIMARY KEY,
    person_id INTEGER NULL REFERENCES people(id) ON DELETE SET NULL,
    label TEXT NOT NULL,
    similarity REAL NULL,
    matched INTEGER NOT NULL,
    camera_status TEXT NOT NULL,
    created_at TEXT NOT NULL
)
```

所有写操作使用参数化 SQL。用户输入不会直接拼接进 SQL。

## 测试

运行完整测试：

```powershell
python -m pytest -q
```

验证模型、OpenCV、PySide6 和 SQLite：

```powershell
python tools\verify_install.py
```

`tests/test_face_engine.py` 会实际加载 YuNet 和 SFace 模型，并使用空白帧执行一次检测，确认模型文件可用。

## 构建 Windows 便携版

安装开发依赖后运行：

```powershell
python -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File tools\build_portable.ps1
```

构建脚本会：

1. 安装运行和构建依赖。
2. 验证 OpenCV、PySide6、SQLite 与两个模型。
3. 运行自动测试。
4. 使用 PyInstaller 生成目录式便携版。
5. 将结果放到：

```text
发布版/人脸识别/FaceVault.exe
```

最终的 `FaceVault.exe` 是一个很小的启动器，真正的 Qt/OpenCV 运行环境放在同级 `runtime` 文件夹。启动器会把运行环境安全同步到 `C:\Users\Public\FaceVaultRuntime` 的 ASCII 路径后再启动，以兼容中文目录和 U 盘路径。

用户的 `FaceVaultData` 和 `FaceVault.config.json` 仍然保存在可见的“人脸识别”文件夹中，不会写进临时运行目录。

## 复制到 U 盘

1. 等待构建完成。
2. 关闭正在运行的 FaceVault。
3. 将整个 `发布版/人脸识别` 文件夹复制到 U 盘。
4. 在目标电脑上双击 `FaceVault.exe`。
5. 首次运行时 Windows 可能询问相机权限，请按需允许。

不要只复制 `FaceVault.exe`。便携版的 Qt、OpenCV、Python 运行库和模型位于同级的 `runtime` 文件夹中。必须复制整个 `人脸识别` 文件夹。

如果把该文件夹复制到 U 盘后，数据也会保存在 U 盘上的 `FaceVaultData` 中。请妥善保管 U 盘，因为其中包含人脸特征数据。

## 常见问题

### 双击 EXE 后没有画面

- 检查摄像头是否被会议软件、相机应用或另一个 FaceVault 实例占用。
- 在 Windows 设置中检查相机权限。
- 在 Settings 中将 Camera Selection 从 `0` 切换到 `1`、`2` 等。
- 查看 `FaceVaultData/logs/facevault.log`。

### 模型加载失败

确认以下两个文件存在且完整：

```text
runtime/_internal/resources/models/face_detection_yunet_2023mar.onnx
runtime/_internal/resources/models/face_recognition_sface_2021dec.onnx
```

源码运行时执行：

```powershell
python tools\download_models.py
python tools\verify_install.py
```

### 总是显示 Unknown

- 光线太暗、侧脸过多、人脸过小或模糊。
- 录入样本角度不足，建议重新录入。
- 识别阈值过高，可以在 Settings 中逐步降低，例如从 `0.42` 调到 `0.38`，但需要承担更高误识别风险。
- 确保摄像头编号和实际使用的摄像头一致。

### 识别成了别人

- 提高 Recognition Threshold。
- 增加 Stable Frames，例如从 4 增加到 6。
- 使用不同人员和不同时段的样本测试阈值。
- 不要把识别结果用于高风险身份认证。

### 为什么人物头像不是照片？

这是隐私设计。SFace 识别不需要长期保存原始照片，因此程序只显示由姓名生成的缩写头像，避免把生物特征照片留在磁盘上。

### 为什么不是把所有运行库塞进一个 EXE？

PySide6 和 OpenCV 的 DLL 对中文路径兼容性不一致。FaceVault 使用一个轻量启动器，先把运行环境同步到固定的 ASCII 目录，再启动真正的桌面程序。这样既能双击中文文件夹中的 EXE，又能让数据库继续保存在 U 盘上的“人脸识别”文件夹内。

### U 盘拔出会导致什么？

如果程序已关闭，没有影响。如果程序正在运行，数据库写入可能中断。请先关闭 FaceVault，再使用 Windows“安全删除硬件”。

## 性能与线程

- Qt 主线程只负责界面绘制和用户交互。
- 摄像头、YuNet 检测、SFace 特征提取和数据库历史写入在后台线程执行。
- Recognition 页面显示 `FPS` 和 `Processing Time`。
- 处理 1080p 输入时，程序保留摄像头原始分辨率，同时可将宽于 960 像素的推理帧等比例缩小以提高速度；检测框会映射回原始画面。
- 多人脸会逐个检测和识别，人数越多，单帧耗时越高。

## 安全边界

本项目明确不实现：

- 偷拍
- 后台偷偷开启摄像头
- 绕过 Windows 摄像头权限
- 隐藏摄像头使用状态
- 自动识别陌生人身份
- 根据人脸推断年龄、性别、种族、健康状况等敏感属性
- 把人脸数据上传到第三方服务器

## 第三方组件和模型

- PySide6：按 Qt/PySide 许可证使用。
- OpenCV：Apache-2.0。
- OpenCV Zoo YuNet 与 SFace 模型：请同时查阅 OpenCV Zoo 对应目录的许可证和模型卡。
- 本项目在分发到第三方前，应再次核对全部依赖和模型的许可证、隐私义务与当地生物特征数据法规。

## 目录名和便携性说明

项目根目录名使用中文 `人脸识别`，便于在桌面和 U 盘上识别。内部软件品牌仍为 **FaceVault**，副标题为 **Private Face Recognition System**。

建议保留 `FaceVault.exe` 文件名，不要单独移动其中的运行库文件。

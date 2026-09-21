# C5 / C7 实现与交接说明

本次提供 C5 文件工具和 C7 本地联调环境。默认使用本地存储与 FakeLLM，
**不需要先开通阿里云或 AWS，也不需要 LLM API Key**。AWS 对应服务叫 **S3**，
阿里云对应服务叫 **OSS**；两种云存储适配均可选。

项目原有分工表写的是 Tom 负责 C7、Robin 负责 C3 并支持 C5。本次代码支持 C5/C7，
不自动修改团队原有人员分工。方案中的文件功能是工程扩展，不能据此把它说成原始提案
已经强制要求的功能。

## 已交付内容

| 范围 | 内容 |
|---|---|
| C5 文件上传 | TXT、PDF、DOCX、PNG/JPEG；类型、文件名和大小检查；SHA-256；会话内文件元数据 |
| C5 解析 | 文本、PDF 页码、Word 正文段落/表格位置；可选 OCR；部分成功、需要 OCR 和失败状态 |
| C5 导出 | 用户明确批准当前摘要后生成 PDF/DOCX；拒绝未批准或旧版本摘要 |
| C5 存储 | 私有本地目录、AWS S3、阿里云 OSS；上传、读取、下载、删除；后端代理下载 |
| C5 调用接口 | FastAPI HTTP API 与 Python `DocumentService`；英文示例供其他组员直接接入 |
| C7 环境 | setup/start/reset/smoke 脚本；默认离线联调；Docker Compose 可选；待启用的 GitHub Actions 模板 |
| C7 文档 | 实现规格、环境说明、参数/云配置、工具调用和本交接文档 |

这里的 tool 是后端 Python 工具和 HTTP API，并非已经部署的 MCP server，也没有自动
注册成任何大模型平台的 function calling 工具。

## 本地怎么跑

Python 3.11+，macOS/Linux/WSL2；Windows 原生环境可使用 Docker 或 WSL2。
在仓库根目录执行：

```bash
./scripts/setup.sh
./scripts/start.sh
```

打开 <http://127.0.0.1:8000/docs> 查看和调试 API。另开终端运行：

```bash
backend/.venv/bin/python scripts/smoke.py
```

默认 smoke 用临时本地目录和进程内 API：创建合成会话 → 上传/解析 Word → 填写信息 →
完成摘要 → 验证未批准导出被拒绝 → 批准当前摘要 → 导出 PDF/DOCX → 下载和删除。
它不使用真实云账户，不需要数据库或真实患者文件。初次安装依赖需要联网。

检测已经运行的本机服务：

```bash
backend/.venv/bin/python scripts/smoke.py --base-url http://127.0.0.1:8000
```

这个命令使用运行中服务的实际存储设置；如果服务连接云桶，就会对该桶执行合成文件的
上传/下载/删除。合成会话会留在内存中，重启后消失。

## 到底需要配置什么

| 使用方式 | 必需配置 |
|---|---|
| 默认本地联调 | 无需密钥；`backend/.env.example` 已有可运行默认值 |
| AWS S3 | SDK、私有 Bucket、Region、IAM 身份/凭证、`DOCUMENT_API_TOKEN` |
| 阿里云 OSS | SDK、私有 Bucket、匹配的 Region/Endpoint、RAM/STS 凭证、`DOCUMENT_API_TOKEN` |
| OCR | Python OCR 依赖、Tesseract 和对应语言包；打开 `DOCUMENT_OCR_ENABLED` |
| 额外 PDF 字体 | 仅默认字库不能覆盖文字时设置 `C5_PDF_FONT_PATH` 为合适的 TTF 文件 |

配置文件是 `backend/.env`，不要提交。云存储 Python SDK 安装：

```bash
./scripts/setup.sh --cloud
```

切换 `STORAGE_BACKEND=s3` 或 `oss`，然后按
[完整存储配置说明](storage-configuration.md) 填写参数。该文档含全部变量、默认限制、
IAM/RAM 最小权限示例、健康检查所需权限，以及阿里云中国内地区域的自定义域名限制说明。
目前没有替你创建收费桶、上传真实文件或验证你的真实云账户。

文件走「浏览器 → FastAPI → 私有存储」，浏览器不需要云存储 SDK、云密钥或 Bucket
CORS 设置。`DOCUMENT_API_TOKEN` 是联调共享密钥，不是患者账户认证；不要把密钥放进
公开发布的前端包。现有 session/GET summary 接口仍未实现用户认证，因此提供的环境只
绑定本机地址，不应直接当作公网医疗服务部署。

OCR 默认关闭。需要时安装 Tesseract 与语言数据，并运行：

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-ocr.txt
```

再设置 `DOCUMENT_OCR_ENABLED=true`，英文用 `eng`；已装简体中文语言包时可用
`eng+chi_sim`。OCR 有识别误差，前端必须显示警告并保留人工核对。

## 别人怎么调用你的 tool

把 [C5 tool 调用文档](c5-tools.md) 发给其他组员，接口总表见
[API contract](api-contract.md)。核心流程是：

1. C1/C3 创建会话，得到 `session_id`。
2. `POST /api/sessions/{session_id}/documents`，multipart 字段名为 `file`。
3. 使用返回的 `document_id` 调用 `POST .../documents/{document_id}/extract`。
4. 读取 `extraction.chunks` 的文字、来源位置和识别方式，同时处理 `warnings`。
5. 摘要完成后，GET summary，展示全文给患者。
6. 患者明确批准时，POST `.../summary/approve`，提交 GET 返回的 `content_sha256`。
7. POST `.../exports`，JSON 为 `{"format":"pdf"}` 或 `{"format":"docx"}`。
8. 使用返回文档 ID 调用 `GET .../documents/{document_id}/download` 下载。

文件解析不会自动修改患者字段、调用 LLM 或生成诊断。C3/C4 如需使用文件内容，应保留
`document_id + sha256 + location` 来源，再走原有字段验证/患者确认流程。
C2 展示最终摘要前应检查 `approved`；完成会话不等于患者已批准摘要。

后端内直接调用可从 `app.utils.document_service` 导入 `DocumentService` 或共享的
`get_document_service()`。完整构造示例、函数签名、错误处理和 C6 存储接口均在英文文档。
不要为每个请求新建一个内存元数据仓库，否则之前上传的文档会找不到。

## 还需要其他组件接什么

- **C1/C2：** 上传、来源/警告展示、摘要确认和下载按钮；患者/医生身份和权限。
- **C3/C4：** 文件证据如何进入可信字段验证；真实 LLM 适配和评估。当前用 FakeLLM。
- **C6：** 会话、摘要版本/批准记录、文件元数据的持久化 DAO、事务与清理策略。

当前所有会话、摘要和文件元数据都在内存中。**重启会丢元数据，但本地或云上的文件字节
可能仍存在**。所以使用单个 worker，不把仅有对象存储误认为数据库已经完成。
`DATABASE_URL` 目前是预留设置，没有需要执行的迁移命令。

开发清理优先在服务运行时通过 DELETE 接口删除文件。清空默认本地测试目录时，先停止
后端，再运行：

```bash
backend/.venv/bin/python scripts/reset_dev_data.py --yes
```

该脚本只删除当前仓库的 `backend/.data/objects`，拒绝符号链接路径，不会根据 `.env`
删除任意目录，也不会删除云桶。自定义目录、云对象和启用版本控制后保留的旧版本，需要
所有者自行配置明确的生命周期或清理方式。

## 验收与限制

- 本地 225 项测试、默认离线 smoke 和实际 HTTP 服务 smoke 均已通过。
- pytest 覆盖原有核心逻辑、文档解析/渲染、存储和接口边界。
- `ci/backend.yml` 提供 Python 3.11/3.12 测试及 smoke 模板，**尚未启用，也没有声称 GitHub CI 已运行**。
- 云适配使用替身测试；真实 Bucket、网络和账户权限仍须配置后单独验证。
- Docker 文件提供可选运行方式；是否构建成功需以实际 Docker 环境验证为准。
- 这些是工程联调验证，不代表真实医疗场景验证，也不替代原方案中的完整评估任务。

团队可优先用默认本地模式完成联调，再决定是否需要云端合成数据演示。

## 合并后如何启用 CI

当前发布凭证没有修改 GitHub Actions workflow 的权限，GitHub 拒绝上传活跃 workflow。
因此将配置保留为 `ci/backend.yml`，供本次 PR 审阅。代码与本地测试不受影响。

本次 PR 合并后，由具有 workflow 修改权限的维护者在更新后的仓库执行：

```bash
git switch develop
git pull --ff-only
git switch -c chore/enable-backend-ci
mkdir -p .github/workflows
cp ci/backend.yml .github/workflows/backend.yml
git add .github/workflows/backend.yml
git commit -m "ci: enable backend tests and synthetic smoke"
git push -u origin chore/enable-backend-ci
```

再向 `develop` 提交并合并启用 CI 的 PR。使用 classic PAT 时，上传 workflow 文件的凭证
需要 `workflow` scope。启用后查看 Actions 的实际运行结果；模板存在不等于 CI 已通过。
英文步骤见 [setup](setup.md#enable-github-actions-after-merge)。

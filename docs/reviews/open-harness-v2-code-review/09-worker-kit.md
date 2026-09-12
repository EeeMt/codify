# 09 Worker Kit 制品、安装与校验 —— Code Review

## 0. 范围

| 项 | 值 |
|---|---|
| 提交区间 | `8081c946^..cbad9e56`（`dev @ cbad9e56`，2026-09-12） |
| 主要文件（diff 行数） | `deploy/worker-kit/verify-runtime.sh` (+292/-69)、`verify-kit-content.py` (+422 新增)、`validate-runtime-manifest.py` (+302 新增)、`verify-cli-payloads.sh` (+210 新增)、`export-archive.py` (+121 新增)、`export.sh` (+107/-17)、`install.sh` (+218/-10)、`bridge-selfcheck.sh` (+10 新增)、`launcher/main.go` (+101/-2)、`deploy/Dockerfile.worker-kit` (+120) |
| 交叉核查文件（只做接口一致性） | `deploy/offline-bundle/scripts/{install-worker-kit.sh,verify-worker-runtime.sh,package-bundle.sh,validate-kit-archive.py}`、`deploy/worker-entrypoint/verification.sh`、`backend/app/core/worker_kit_inventory.py`、`backend/app/core/worker_runtime_readiness.py`、`backend/app/api/worker_profiles.py`、`backend/app/core/worker_task_lifecycle.py` |
| 审查方法 | 静态阅读当前 HEAD 完整文件（非仅 diff）+ 契约/不变量对照（`docs/superpowers/specs/2026-09-03-worker-kit-validation-boundary-design.md` §3/§5/§9、`docs/worker-kits.md`）+ 3 个窄范围可执行实验 + 与后端 inventory/receipt 消费者逐字段交叉核对 |
| 实际运行的实验 | ① `bash -c 'set -e; if ! f; then …'`（函数内 errexit 语义）；② `tarfile.open(mode="w:gz")` 连续两次写入同一内容比对字节；③ 构造含两个 `manifest.json` 成员的归档，跑 `verify-kit-content.py --archive` 并用 `tar -xzf` 解包比对 |
| 未覆盖 | `model-proxy/main.go` 内部实现（T10）、Runtime Bundle 构建/readiness/CAS（T08）、offline-bundle 打包与部署编排（T15）、测试质量（T16）；未执行任何 `docker build`/Kit 安装/`verify-runtime`（无 Docker daemon 与 root 环境） |

## 1. 结论摘要

| 判定 | 数量 |
|---|---|
| FIX_NOW | 0 |
| FIX_IF_CHEAP | 5 |
| DEFER | 4 |
| ACCEPT/CLOSE | 5 |

Kit 侧校验链**结构**完整且自洽：归档名嵌入 manifest SHA 前缀、解包前后两次内容清单校验、present/absent 语义与后端一致、Runtime Bundle 与 Kit/镜像 identity 双向绑定、安装锁 + 原子 rename 保证不可覆盖，未发现 zip-slip、绝对路径逃逸或任何内容绕过与凭据泄漏。无 FIX_NOW；需要现在修的是 5 条 FIX_IF_CHEAP（KIT-01、KIT-03、KIT-04、KIT-05、KIT-INFO-03），全部是 ≤ 数行的定点修正。其余 9 条按内部离线、约 3 名用户的 beta 画像书面接受（DEFER 4 条、ACCEPT/CLOSE 5 条），触发前提在当前部署形态下不成立或影响已有上游兜底。

## 2. 问题清单

### KIT-01 逐 Harness bridge 自检的失败被静默丢弃，该门禁实际不生效
- **判定**：FIX_IF_CHEAP —— 不阻断安装或执行
- **位置**：`deploy/worker-kit/verify-runtime.sh:195`（提交 `df799c64`）
- **证据**：`run_one()` 在整个脚本中只以 `if ! run_one "${adapter_key}" "${path}"; then …`（`verify-runtime.sh:315`）形式调用。按 bash 语义，函数在 `!` 取反的条件上下文中执行时，其**函数体内的 errexit 被整体抑制**（已实测：`set -e; f(){ false; echo inside; }; if ! f; then echo fail; else echo ok; fi` → 输出 `inside` + `ok`，函数返回 0）。因此 `verify-runtime.sh:194-195` 的
  `docker run --rm … --entrypoint "/opt/codify-kit/bridge-selfcheck-${key}" "${IMAGE}" "${path}"`
  既无 `|| return 1` 也无状态捕获，其非零退出被忽略，`run_one` 的返回值只由末尾的 launcher `--verify`（`:206`）决定。同文件其它步骤（`:177`、`:185`、`:191`、`:194`）都显式写了 `return 1`，唯独这一步没有，属实现遗漏。
  该缺陷在 host_mount 分支必然触发：`:195` 的命令**没有挂载** `${HARNESS_HOST_PATH}:${HARNESS_CONTAINER_PATH}`（挂载只加在后面 launcher 的 `args` 里，`:199-202`），此时 `${path}` 是宿主 override 的容器路径，容器内不存在该文件，`bridge-selfcheck.sh` 的 `test -x` 必然失败——失败却被丢弃。
- **影响**：设计文档 §5.3/§9.1 要求"每个 present Harness 过 integrity + self-check + launcher --verify"，实际 self-check 结果对最终退出码没有任何影响：`bridge-selfcheck.sh` 校验的是 `"${cli}" --version` 的**退出码**，而 pi/opencode/codex 的 `adapter_verify_runtime` 只要求版本输出非空（`deploy/worker-entrypoint/harness/adapters/pi.sh:53-57`、`opencode.sh:54-58`、`codex.sh:63-67`，stderr 丢弃后只看 stdout），因此"能打印版本但进程非零退出"的 CLI 会同时通过 launcher 门禁、而其唯一的拦截者（self-check）被丢弃 → `verify-runtime.sh` 整体退出 0，Profile 被标记为已校验；admin 校验通过后才会允许创建 V2 Task。
- **最小动作**：host_mount 分支**显式跳过**自检（该分支未挂载 `${HARNESS_HOST_PATH}`），其余分支加 `|| return 1`（各 1 行）——照原建议无条件加会让 break-glass 流程必然变红
- **验证**：`bash -c` 复现 errexit 语义已实测；修复后可用 host_mount 形式跑 `verify-worker-runtime.sh --harness-host-path …`，观察 self-check 失败时整体退出码变为 1。本次未运行 docker（无 daemon）。

### KIT-03 LD_LIBRARY_PATH 隔离"硬门禁"可静默跳过，与文档声称的"每对 Kit+镜像都证明"不符
- **判定**：FIX_IF_CHEAP —— 真正保证在 launcher 的 `main.go:263`
- **位置**：`deploy/worker-kit/verify-runtime.sh:221-229`（提交 `be7541f7`）
- **证据**：探测 libc 目录的命令带 `2>/dev/null || true`（`:221-225`），随后
  `if [ -z "${lib_dir}" ]; then echo "…skipping LD_LIBRARY_PATH isolation gate" >&2; return 0; fi`（`:226-229`）
  即探测失败（镜像无 `/bin/sh`、docker 执行错误）与"镜像确实没有 glibc"被当作同一种情况，直接 `return 0` 判定通过；调用点 `:301-303` 只在返回非零时 `exit 1`。触发面并不罕见：探测循环匹配 `/lib/*/libc.so.6`、`/usr/lib/*/libc.so.6` 等路径，musl 系镜像（Alpine，`docs/worker-kits.md:23` 明确把 Alpine 列为需要关注的场景）永远匹配不到，于是该"Hard gate"对整类镜像从不执行。而 `docs/worker-kits.md:20-24` 声称 "`verify-runtime.sh` replays the polluting environment through the real launcher to prove this contract for each Kit+image pair"。
- **影响**：管理员/CI 得到的 `verify-runtime` 成功结论不包含该契约的证明；若某 Kit 的 launcher 未 unset `LD_LIBRARY_PATH`（老 Kit 版本），在探测被跳过的镜像上不会被发现，失败推迟到 Task 运行时（store 内二进制启动即报 undefined-version），与设计 §6 "失败必须在 Harness exec 之前"相悖。
- **最小动作**：去掉探测命令的 `|| true`，改为 `lib_dir="$(…)" || { echo probe failed; return 1; }`（2 行）
- **验证**：静态阅读 + 与文档声明比对。musl/glibc 镜像的实际行为未运行验证。

### KIT-04 `--archive` 校验容忍重复的 `manifest.json` 成员，导致"被校验的 manifest"与"被安装/消费的 manifest"可能不是同一份字节
- **判定**：FIX_IF_CHEAP
- **位置**：`deploy/worker-kit/verify-kit-content.py:260-264`（提交 `1905abda`）；消费侧 `:372-380` 与 `install.sh:106-107`
- **证据**：`archive_inventory()` 中
  ```python
  relative = _archive_relative(member.name, root_name)
  if relative is None or relative in EXCLUDED_PATHS:
      continue
  if relative in seen:
      raise ValueError(f"duplicate Worker Kit content path: {relative!r}")
  ```
  排除路径（`EXCLUDED_PATHS = {"manifest.json", ".install-receipt.json", ".smoke-passed"}`，`:23`）在**重复检测之前**就 `continue`，因此归档里可以出现多个 `manifest.json` 而不报错；`verify_archive()` 用 `next(member for member in bundle.getmembers() if member.name == f"{root_name}/manifest.json")`（`:374-380`）取**第一个**成员做身份/内容清单校验，而 `tar -xzf` 落盘的是**最后一个**成员。实测（构造归档：成员序 = 合法 A、合法 B，B 仅 `kit_version` 不同）：
  `python3 deploy/worker-kit/verify-kit-content.py --archive dup.tar.gz --root-name 0.1.0-linux-amd64-deadbeef1234` → `rc=0`（校验 A，digest 前缀 `4b1f54bca026`）；`tar -C out -xzf dup.tar.gz` 后 `out/…/manifest.json` 的 `kit_version = "9.9.9-攻击"`（B，digest 前缀 `444475996e1e`）。
- **影响**：`install.sh:139-141`（归档名前缀）用的是**解包后** manifest 的摘要，`package-bundle.sh:63-70` 与 `preflight-v2-release.sh:74-78` 用 `{member.name: member}` 字典（后者覆盖前者）读的又是**最后一个**，于是"归档校验通过"并不等于"安装/消费的 manifest 被校验过"。content inventory 本身不包含 `manifest.json`，所以元数据字段（`kit_version`、`runtime_bin`、`bash`、`entrypoint`、`components`）可以在两成员间不同而不触发任何校验；仓库自身构建产物（`export-archive.py` 每个成员只写一次）不受影响，这是校验器的 fail-open 缺口而非现实构建路径的缺陷。
- **最小动作**：`seen.add` 前移到 `EXCLUDED_PATHS` 的 `continue` 之前（1 行）
- **验证**：已按上述构造实测。建议同时补一条断言：同一成员名出现两次即抛 `duplicate Worker Kit content path`。

### KIT-05 归档名缺少 `codify-worker-kit-` 前缀仍可安装，但后端 receipt 校验要求完全一致
- **判定**：FIX_IF_CHEAP
- **位置**：`backend/app/core/worker_kit_inventory.py:398-403`（提交 `1905abda`，T08 文件，此处仅记接口不一致）
- **证据**：`validate_installer_managed_kit_provenance()` 要求
  `expected_archive = f"codify-worker-kit-{expected_name}.tar.gz"` 且 `receipt["archive"] == expected_archive`；而 `install.sh:63-64` 只做 `KIT_NAME="${KIT_NAME#codify-worker-kit-}"`（前缀不存在时原样保留）、`:76-81` 的正则 `^.+-(linux-[A-Za-z0-9_.-]+)-([0-9a-f]{12})$` 也不要求该前缀，receipt 的 `archive` 字段直接写 `$(basename "${ARCHIVE}")`（`install.sh:221-233`）。因此把 `codify-worker-kit-0.6.17-linux-amd64-<12hex>.tar.gz` 重命名为 `mykit-0.6.17-linux-amd64-<12hex>.tar.gz` 后：安装成功、目录名合法，但 readiness/Profile 校验会以 `install receipt does not match its manifest or path` 判为 `worker_kit_invalid`。
- **影响**：operator 一次重命名（例如从发布页下载后改名）会得到一个"装上但永远无法 verify"的 Kit；由于 content-addressed 目录**拒绝覆盖**（`install.sh:72-75`、`:235-252`），恢复必须由 root 手工删除目录，属于容易踩且不可自愈的运维陷阱。
- **最小动作**：安装器断言 `basename(ARCHIVE) == codify-worker-kit-*.tar.gz`（1 行；两侧安装器各 1 行）
- **验证**：静态对照两处字符串契约；本条未端到端复现（需 root + docker）。

### KIT-INFO-03 文档中的 Kit 路径示例仍是不带摘要前缀的旧命名
- **判定**：FIX_IF_CHEAP —— 操作者一年要读几次文档
- **位置**：`docs/worker-kits.md:256,265,312`
- **说明**：示例为 `/opt/codify/worker-kits/0.4.0-linux-amd64`，而 content-addressed 安装目录为 `<version>-linux-<arch>-<12hex>`，且后端 `validate_installer_managed_kit_provenance` 要求 basename 必须等于该命名。文档示例照抄会导致 Profile 校验失败。
- **最小动作**：改 `docs/worker-kits.md` 三处示例为 `<version>-linux-<arch>-<12hex>`

### KIT-02 两个安装器同源漂移：文档化的离线安装路径缺少模型代理与 harness inventory 的 fail-closed 校验
- **判定**：DEFER —— 检查强度偏弱，非装不上
- **位置**：`deploy/worker-kit/install.sh:120-135`、`:158-204`（提交 `42075f73`）对比 `deploy/offline-bundle/scripts/install-worker-kit.sh:100-108`（最后修改 `1905abda`）
- **证据**：两份脚本是同一"可信安装"边界的近乎逐行复制（`diff` 显示除措辞、`jq`/python 选择、verifier 定位外结构相同），但 `deploy/worker-kit/install.sh` 在 `42075f73`（2026-09-11，模型代理落地）新增了两组门禁而离线安装器未同步：
  1. 模型代理：`MODEL_PROXY_PATH`/`MODEL_PROXY_SHA256` 必须等于 `/opt/codify-kit/bin/codify-model-proxy` 与清单摘要（`install.sh:120-133`），离线安装器**完全没有**这段；
  2. harness inventory：`.harness_inventory | keys | length == 4`、present 条目必须存在/可执行/size 与 sha256 相符、absent 条目不得携带 `harness/<key>/` 载荷目录（`install.sh:157-204`），离线安装器**完全没有**这段（只有 `test -x launcher`/`test -s manifest.json`/`test -d nix/store`/`test -f verify-kit-content.py`，`:100-108`）。
  而离线安装器才是文档指定的生产路径：`docs/DEPLOYMENT.md:255-258`、`docs/worker-kits.md:228`、`deploy/offline-bundle/README.md:62`、`docs/runbooks/multi-harness-rollout.md:79` 均指向 `./scripts/install-worker-kit.sh`；`deploy/worker-kit/install.sh` 甚至不在离线 bundle 内（`package-bundle.sh:96` 只 `cp -R deploy/offline-bundle`）。
- **影响**：a) 通过文档路径安装的 Kit 可以缺失或篡改 `bin/codify-model-proxy`（清单 path/sha 不一致、文件不可执行、或与清单 sha 不符）而安装成功；后端 inventory 消费者不读取 `model_proxy` 字段（`grep -rn model_proxy backend/app` 无命中），Task 热路径也只校验**所选 CLI** 的字节（`launcher/main.go:275-281`），因此唯一的后续拦截是管理员显式 `verify-runtime`；b) 两份脚本的"同源"约定没有任何机制保证，下一次单边修改会继续扩大差异（已有先例：`42075f73` 只改了其中一份）。
- **最小动作**：把 `manifest.model_proxy` 一致性 + present payload 可执行位断言移进两边都已调用的 `verify-kit-content.py --root`（约 10 行 Python，零复制）；不要复制 85 行 shell
- **验证**：静态 `diff` 两文件已确认缺块；补齐后可对同一构造 Kit 分别跑两个安装器，断言两者均拒绝 missing/invalid model proxy。

### KIT-06 Kit 侧校验器与后端 inventory 契约宽严不一致（路径归一化 / 额外字段）
- **判定**：DEFER
- **位置**：`deploy/worker-kit/verify-runtime.sh:77`、`deploy/worker-kit/install.sh:167` 对比 `backend/app/core/worker_kit_inventory.py:160-237,239-260`
- **证据**：Kit 侧只断言 `path.startswith('/opt/codify-kit/')`（`verify-runtime.sh:77`），安装时用 `sub("^/opt/codify-kit/"; "")` 直接拼路径（`install.sh:167`），因此 `/opt/codify-kit/harness/pi/../../bin/pi` 这类含 `..` 的路径会被 Kit 侧全链接受（`run_one` 只判是否以 `/` 开头，`:184-186`；容器侧 `verification.sh:112-118` 也只做 `case "${path}" in /opt/codify-kit/*)`）。后端 `kit_relative_path()` 显式拒绝任何 `..` 段（`worker_kit_inventory.py:239-260`）；后端的 `validate_harness_inventory()` 还要求 present 条目字段集**恰好**为 `{availability,path,version,sha256,size}`、absent 恰好 `{availability,reason_code}`，Kit 侧校验器对额外字段不作限制。反向地，Kit 侧要求模型代理被 inventoried 恰好一次（`verify-runtime.sh:84-102`），后端不检查 `model_proxy`。
- **影响**：一份"手工改过/打包工具异常"的 Kit 可以通过安装与管理员 `verify-runtime`，却在后端 readiness 处被判 `worker_kit_invalid`（`worker_runtime_readiness.py:1023` 起），而目录不可覆盖 → 只能 root 手工清理。仓库自身构建产物的字段集合与两侧都匹配，故不影响正常发布路径。
- **最小动作**：后端放宽：接受未知字段（删断言）；不要给 Kit 侧补字段集断言
- **验证**：静态对照三处实现；未构造端到端复现（需要可挂载 Kit 的 docker 环境）。

### KIT-08 `install.sh` 的校验和工具回退不完整，无 `sha256sum` 的主机中途失败
- **判定**：DEFER
- **位置**：`deploy/worker-kit/install.sh:45-49` 与 `:130,139,184`
- **证据**：脚本开头为归档校验和提供了 `sha256sum` → `shasum -a 256` 回退（`:45-49`，说明作者考虑了无 coreutils 的主机），但后续模型代理摘要（`:130`）、manifest 摘要（`:139`）、harness payload 摘要（`:184`）都**无条件**调用 `sha256sum`。在 macOS/无 coreutils 主机上（`shasum` 存在、`sha256sum` 不存在时）会在 `:130` 以 `command not found` 触发 `set -e` 中止，报错信息与真实原因无关。`export.sh:201-205`、`package-bundle.sh:49-53` 都保留了同风格的双工具回退，说明这是被遗漏的一处。
- **影响**：仅影响在无 `sha256sum` 的宿主上直接运行 `deploy/worker-kit/install.sh`（生产 Docker Host 通常有 coreutils，故按 DEFER 处理）；错误信息误导排障。
- **最小动作**：抽 `sha256_of()` 复用 3 处（顺手）
- **验证**：静态阅读；未在无 coreutils 环境实跑安装（需 root）。

### KIT-INFO-04 root-only 的安装器测试与 `install.sh` 新增门禁可能已脱节
- **判定**：DEFER
- **位置**：`backend/tests/unit/test_offline_bundle_export.py:988-1075`（T16/T15 范围）
- **说明**：`test_worker_kit_installers_reject_target_appearing_before_atomic_publish` 对两个安装器参数化，构造的合成 Kit **不含** `model_proxy` 与 `harness/`，并断言 `"atomic publish" in stderr`。静态推断：`deploy/worker-kit/install.sh` 会在 `:122` 因缺失 `model_proxy` 提前 `exit 2`，从而到不了锁步骤、stderr 不含该串。该测试在非 root 环境 `pytest.skip`（`_secure_install_root`），CI 不会暴露。**未运行验证**（需 root）。
- **最小动作**：补 fixture（`model_proxy` 字段 + `bin/codify-model-proxy` + `harness/*`）

### KIT-07 导出归档字节不可复现（gzip 头写入当前时间），同一 Kit identity 每次导出摘要不同
- **判定**：ACCEPT/CLOSE —— 无消费者需要字节复现
- **位置**：`deploy/worker-kit/export-archive.py:67-68`（提交 `b54f3267`）
- **证据**：`tarfile.open(archive_path, mode="w:gz")` 使用 `gzip` 默认行为，头部 mtime 取当前时间。实测：用同一 `TarInfo` + 同一内容连续两次 `tarfile.open(fileobj=buf, mode="w:gz")`（间隔 1.2s），字节头 `1f8b08001e36a46a…` vs `1f8b08001f36a46a…`，`a.getvalue() == b.getvalue()` 为 `False`。
- **影响**：`export.sh:201-205` 生成的 `<archive>.sha256` 只是当次构建的产物摘要，无法用于跨次比对/复现（同 identity 的两个归档摘要不同）；release evidence 中的 `archive_sha256` 无法用于"同一 Kit 重新导出是否变形"的判断。不影响安装期校验（当次 `.sha256` 与实际文件一致）。
- **动作**：不改代码（本阶段书面接受并关闭）
- **验证**：已实测。未在真实 Kit 归档上复跑导出（需要 docker build）。

### KIT-INFO-01 全 absent 的 Kit 在 `--verify` 下以退出码 0 结束（未校验任何 Harness）
- **判定**：ACCEPT/CLOSE
- **位置**：`deploy/worker-kit/verify-runtime.sh:305-320`
- **说明**：`ADAPTER_KEYS` 取自 inventory 的 present 键（`:273-299`），四键全 absent 时循环体为空 → `exit 0`（stderr 记录各键 reason_code）。上游另有门禁：`worker_profiles.py:785-809` 在选择某键时抛 `harness_cli_unavailable`。属设计取舍，仅提示"退出码 0"不等于"至少一个 Harness 可用"。
- **动作**：不改代码（本阶段书面接受并关闭）

### KIT-INFO-02 `deploy/worker-kit/install.sh` 依赖仓库内相对路径，不能随离线 bundle 分发
- **判定**：ACCEPT/CLOSE
- **位置**：`deploy/worker-kit/install.sh:105`
- **说明**：`ARCHIVE_VALIDATOR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../offline-bundle/scripts" && pwd)/validate-kit-archive.py"`，而 `package-bundle.sh:96` 只打包 `deploy/offline-bundle`，故该脚本只能在仓库 checkout 内运行；离开仓库时 `cd` 失败并以 `set -e` 中止（错误信息不含具体原因）。与 KIT-02 的"双安装器"问题同源。
- **动作**：不改代码（本阶段书面接受并关闭）

### KIT-INFO-05 launcher 在 `CODIFY_KIT_MANIFEST_SHA256` 为空时跳过所选 CLI 校验
- **判定**：ACCEPT/CLOSE
- **位置**：`deploy/worker-kit/launcher/main.go:265-281`
- **说明**：`if verifyOnly { … } else if expectedKitManifestDigest != "" { verifySelectedCLI(kitHome) }`——未设置该 env 时既不校验 manifest 摘要，也不校验所选 CLI 摘要。V2 writer 均设置该 env（`worker_task_lifecycle.py:698`、`worker_profiles.py:1030-1036`），V1 兼容路径不执行 CLI 校验是刻意的历史行为；提醒：该 env 一旦在 V2 路径漏配，热路径会静默退回"只读 manifest"的旧语义（管理员显式 verify 仍会跑全量 content inventory）。
- **动作**：不改代码（本阶段书面接受并关闭）

### KIT-INFO-06 `model-proxy` 内部实现未审查
- **判定**：ACCEPT/CLOSE —— 非缺陷，审查归 T10
- **位置**：`deploy/worker-kit/model-proxy/main.go`（+420，T10 负责）
- **说明**：本专题只核查它与 Kit 产物的接口（`--version` 输出 `codify-model-proxy <version>` 供 `Dockerfile.worker-kit:94` 的 `awk '{print $2}'` 取版本；`bin/codify-model-proxy` 被 content inventory 与 manifest `model_proxy.sha256` 双重绑定，`Dockerfile.worker-kit:129-132`），未审查其协议合并/请求改写逻辑。
- **动作**：不改代码（本阶段书面接受并关闭）

## 3. 逐项核查记录

| # | 不变量/契约 | 结论 | 依据 |
|---|---|---|---|
| 1 | 校验链逐 manifest adapter（不再写死 claude/codex） | 通过 | 旧的 `case "${HARNESS_KEY}" in claude\|codex)` 白名单已删除；`verify-runtime.sh:294-320` 按 inventory present 键逐个 `run_one`，absent 键在 `:288-296` 记录 reason_code |
| 2 | 每一步失败 fail closed | **部分不通过** | 见 KIT-01（`run_one:194-195` 无状态检查）、KIT-03（`:221-229` `\|\| true` + `return 0`）；其余步骤均为显式 `return 1`/`exit N` |
| 3 | 每 Harness 校验 SHA/字节（非仅存在性） | 通过 | `check_payload_integrity`（`:163-179`）容器内 `sha256sum` + `wc -c` 与 manifest 比对，docker 执行失败时 observed 为空 → 判不等 → `return 1`；`verify-kit-content.py:56-73` 对全量 inventory 逐文件 SHA-256 |
| 4 | 归档路径逃逸（zip-slip/绝对路径/`..`） | 通过（未发现逃逸） | `export-archive.py:31-53`；`verify-kit-content.py:41-54,111-149,219-249`（含把 `/nix/store` 绝对符号链接白名单化）；安装前 `install.sh:105-107` + `validate-kit-archive.py` |
| 5 | 符号链接/硬链接目标必须落在归档或目录内 | 通过 | `_validate_directory_symlinks`/`_validate_archive_symlinks`（`verify-kit-content.py:90-109,138-149`），硬链接解析用 `follow_final_symlink=False`（`:306-330`） |
| 6 | archive 名 ↔ manifest SHA 前缀 ↔ manifest platform 三者一致 | 通过（命名严格性见 KIT-05） | `install.sh:79-81,139-156`；`export.sh:186-188` 由 manifest 摘要生成名字与路径 |
| 7 | 已存在 identity 目录不可覆盖（含并发） | 通过 | `install.sh:72-75` 预检 + `:235-252` flock 内 `os.path.lexists` 再检 + `os.rename` 原子发布；锁文件以 `O_NOFOLLOW` 打开 |
| 8 | 安装根与 Kit 目录 root 属主且不可被 group/others 写 | 通过 | `check_install_root`（`install.sh:21-41`）用 `os.lstat`（拒绝 symlink 根/父）并在 `mkdir` 后二次校验（`:56-60`）；`:61-62` 处理安装根、`:213-214` 落盘后对 Kit 树 `chown -R 0:0` + `chmod -R u=rwX,go=rX`（`=` 形式会清除 setuid/setgid） |
| 9 | present/absent 语义与后端 inventory 一致 | 通过 | Kit 侧 `verify-runtime.sh:66-88` 与后端 `worker_kit_inventory.py:160-237` 均为：四键齐备；present→path/version/sha256/size；absent→reason_code ∈ {not_selected, missing_payload}（字段集严格性差异见 KIT-06） |
| 10 | content inventory 排除集合与摘要算法两端一致 | 通过 | `verify-kit-content.py:23` 与 `worker_kit_inventory.py:73` 均为 `{manifest.json, .install-receipt.json, .smoke-passed}`；`inventory_digest`（`:37-39`）与后端 `content_inventory_digest` 均为"按 path 排序 + `sort_keys` 规范 JSON" |
| 11 | Runtime Bundle ↔ Kit identity ↔ 镜像 identity 绑定 | 通过 | `verify-runtime.sh:118-152`：schema ∈ {runtime-manifest/v2, runtime-bundle/v2}、platform 与 Kit 一致、`RepoDigests`/`Id`/`Os`+`Architecture` 与冻结 identity 一致、`worker_kit_identity.manifest_sha256` 等于挂载 manifest 的实际 SHA-256，再交 `validate-runtime-manifest.py`（`:154-157`）校验字段/摘要/能力矩阵 |
| 12 | 校验器字段覆盖消费者所需字段（runtime bundle） | 通过 | 校验器要求的 `schema/bundle_digest/adapters/files/contract_version/event_schema` 与 launcher 实际读取字段（`launcher/main.go:139-212`）一致；launcher 额外接受 `runtime-bundle/v1` 只出现在未注入 `CODIFY_RUNTIME_VERIFICATION_MANIFEST` 的路径（V1 任务不设该 env），不与校验器冲突 |
| 13 | launcher 平台/版本/manifest 摘要/所选 CLI 摘要 fail closed；exec 与信号语义 | 通过 | `main.go:227-241`（schema_version/manifest_kind/kit_version/platform/必需路径）、`:265-271`（manifest 摘要）、`:273-281`（CLI 摘要，条件见 KIT-INFO-05）、`:286,294`（`syscall.Exec` 替换进程，无独立信号转发问题） |
| 14 | 安装 receipt 字段与后端消费者一致 | 通过（命名严格性见 KIT-05） | `install.sh:218-233` 写入的 8 个字段与 `worker_kit_inventory.py:377-406` 的 required 集合逐项对应；`install.sh:112-116` 的 `STAGED_KIT` 推导与后端 basename 期望相符 |
| 15 | 临时目录与失败清理 | 通过 | `install.sh:87-93` `trap cleanup EXIT`；`export.sh:35-41` 清理 `kit-staging` 并 `docker rm`（并发导出会共用同一 staging 目录，属开发期工具，未列为问题） |
| 16 | 后端 inventory 读取的字段/布局与 Kit 产物一致 | 通过（例外见 KIT-06） | `Dockerfile.worker-kit:96-108` 写出的 manifest 字段集覆盖后端 `validate_content_inventory`/`validate_harness_inventory` 的严格集合；`platform=linux/${TARGETARCH}` 与 launcher 的 `runtime.GOOS/GOARCH` 比对一致 |

## 4. 局限与未验证项

- **未执行任何 Docker/Nix 构建与安装**：本机无 Docker daemon 且非 root，故 `install.sh`/`install-worker-kit.sh` 的端到端行为、`verify-runtime.sh` 的容器内分支（`check_payload_integrity`、`check_library_path_isolation`、逐 Harness `launcher --verify`）均为静态推理，未运行验证。
- **未运行 pytest**：`backend/tests/unit/test_offline_bundle_export.py` 的安装器用例经 `_secure_install_root()` 在非 root 下 `pytest.skip`，本机无法得出有效结论（KIT-INFO-04 为静态推断）。也未运行任何全量构建/测试（按审查纪律）。
- **已运行的三个实验**仅证明语言/库层语义与归档成员选择行为（bash errexit、gzip mtime、重复成员归档），不构成对真实 Kit 归档的验证。
- **未审查**：`model-proxy` 内部（T10）；Runtime Bundle 构建/readiness/CAS/命令平面（T08/T01/T11）；offline-bundle 打包与部署编排（T15）；测试质量（T16）。若这些专题发现 `model_proxy` 或 receipt 命名契约的其他消费者，KIT-02/KIT-05 的影响面需相应更新。
- **未覆盖的宿主差异**：`sha256sum`/`jq`/`python3` 缺失、musl 宿主、非 x86 平台、并发安装的真实表现未验证（KIT-03、KIT-08 相关）。

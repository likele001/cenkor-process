# 推送与公开镜像发布

本文说明 cenkor-process 的两套仓库如何提交、推送和同步。日常开发只碰私有仓；公开仓是"洗过"的镜像，必须用固定流程生成，不能直接推。

## 1. 仓库拓扑

| 角色 | 位置 | 可见性 | 分支 | 说明 |
|---|---|---|---|---|
| 开发主仓 | 服务器 `/www/wwwroot/cenkor-process` | — | `master` | 日常开发、部署都用它 |
| 私有远端 | `git@github.com:likele001/cenkor-process-old.git` | 私有 | `master` | 完整历史，含商业扩展源码 |
| 公开远端 | `git@github.com:likele001/cenkor-process.git` | 公开 | `main` | 洗过历史，无商业扩展、无凭据 |
| 干净快照 | `/tmp/cenkor-process-clean` | — | `main` | 一次性产物，用于推公开仓 |

服务器主仓的 remote 配置：

```bash
git remote -v
# origin  git@github.com:likele001/cenkor-process-old.git   （日常推送目标）
# public  git@github.com:likele001/cenkor-process.git       （公开镜像，只读参照）
```

`master` 跟踪 `origin/master`。`public/main` 只用于查看，不参与开发。

## 2. 日常开发：提交到私有仓

### IDE（远程 SSH 连服务器）

1. 源码管理面板确认分支是 `master`
2. 填写提交信息，点「提交」
3. 点「同步 / 推送」，目标选 `origin`（不是 `public`）
4. 确认推送后 `master` 与 `origin/master` 同 hash

### 命令行

```bash
cd /www/wwwroot/cenkor-process
git status                 # 确认没有意外改动
git add <具体文件>          # 建议按文件名添加，不用 git add -A
git commit -m "<type>(<scope>): <说明>"
git push                   # 等价于 git push origin master
git status --short --branch
```

提交前自查：

- `backend/extensions/` 下已安装的商业扩展应被忽略（用 `git status --ignored` 才能看到，普通 `git status` 不显示被忽略文件），**不要** `git add -f`
- `.env`、`.env-bak*` 一律不入库；`.gitignore` 对**已跟踪**文件无效，若 `git ls-files | grep '\.env'` 有输出，先 `git rm --cached <文件>` 清理
- 不提交 `dist/`、日志、临时脚本

## 3. 公开镜像同步

触发时机：私有仓已推送、需要对外发布最新代码时。

```bash
# 1) 从私有仓重新拉一份干净克隆
rm -rf /tmp/cenkor-process-clean
git clone --no-local git@github.com:likele001/cenkor-process-old.git /tmp/cenkor-process-clean
cd /tmp/cenkor-process-clean

# 2) 剔除商业扩展路径与遗留的 .env 备份 + 替换历史中的凭据
#    下面 3 条 --path 加 redact 规则是过滤参数基线，改动会导致历史整体重写
cat > /tmp/redact.txt <<'EOF'
<旧数据库密码>==>REDACTED_DB_PASSWORD
EOF

git filter-repo \
  --path backend/extensions/dashboard_report \
  --path backend/extensions/order_planning \
  --path backend/.env.bak-20261010-202341 \
  --invert-paths \
  --replace-text /tmp/redact.txt \
  --force

# 3) 推送前校验（全部通过才继续）
git rev-list --count HEAD                                  # 快照提交数，允许少于私有仓（空提交被剪掉）
git log --all --oneline -- backend/extensions/dashboard_report backend/extensions/order_planning backend/.env.bak-20261010-202341 | wc -l  # 应为 0
git ls-files | grep -E '(^|/)\.env$|env\.bak' || true      # 树中不应有 .env / .env.bak*（.env.example 除外）
git grep -n '<旧数据库密码>' -- . || true                  # 当前树：应无输出
git log --all --oneline -S'<旧数据库密码>' | wc -l         # 历史：应为 0

# 4) 切到公开分支并推送
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin git@github.com:likele001/cenkor-process.git
git fetch origin main
git remote -v                                              # 确认 origin 指向公开仓
OLD_PUBLIC=$(git rev-parse origin/main)                 # 记录旧值，防止覆盖他人推送
git push --force-with-lease=main:$OLD_PUBLIC origin main # 改过过滤参数 → 历史整体重写
# 过滤参数未变且确认 fast-forward 时，可用：git push -u origin main
```

要点：

- 每次同步都**从私有仓重新 clone 再洗**，不要复用上一次的 `/tmp/cenkor-process-clean` 直接改
- 过滤参数基线：2 个商业扩展路径 + `backend/.env.bak-20261010-202341` + 1 条 `redact.txt` 替换规则。该备份曾被提交且含真实旧密码，必须连路径一起剔除；仅靠 `--replace-text` 打码仍会公开连接串
- `filter-repo` 是确定性的：历史只追加、过滤参数不变时，旧提交的改写 hash 保持一致，正常是 fast-forward，无需 force
- 如果重洗时改过过滤参数（增减路径、改替换规则），历史 hash 会整体变化，需要 `git push --force-with-lease`，推送前先 `git fetch origin main` 并记录旧值

## 4. 红线

1. **绝不把 `master` 推到 `public`**。两套历史无关，推上去会把含商业扩展源码与旧凭据的历史暴露出去。
2. **绝不 `git add -f backend/extensions/`**。已安装扩展属于交付物，不入仓。
3. **绝不提交 `.env` / `.env.bak*`**。真实 `DB_URL` 只存在于服务器 `backend/.env`（644，本地可访问）；已跟踪的历史遗留备份要用 `git rm --cached` 清理，不能只加 `.gitignore`。
4. 公开仓一旦泄漏凭据或闭源代码，需立即：轮换数据库密码 → 重新洗历史 → `--force-with-lease` 覆盖远端。

## 5. 常见故障

| 现象 | 原因 | 处理 |
|---|---|---|
| `! [rejected] master -> master (non-fast-forward)` | 远端有新提交 | `git pull --rebase origin master` 后重新推送 |
| `refusing to update checked out branch` | 往非裸仓（如服务器路径）推送 | 只向 GitHub 远端推送，不要以服务器目录为 remote |
| `fatal: refusing to merge unrelated histories` | 误把 `master` 与 `public/main` 关联 | 放弃该操作，二者永不合并 |
| 公开仓 push 被拒 | 历史被重写 | 先 `git fetch origin main` 记录 `OLD_PUBLIC`，再用 `git push --force-with-lease=main:$OLD_PUBLIC origin main` |
| `git filter-repo` 后 remote 消失 | 工具默认清理 remote | 重新 `git remote add` + `git fetch` |

## 6. 发版前检查清单

- [ ] 服务器 `git status` 干净，`master` 与 `origin/master` 同 hash
- [ ] 私有仓已推送成功
- [ ] 干净快照历史可由私有仓按固定过滤参数复现（提交数允许略少：变空的提交会被剪掉）
- [ ] 历史中商业扩展路径与 `.env.bak` 备份路径命中 0
- [ ] 当前树 `git grep` 与历史 `git log -S` 均无凭据命中，树中无 `.env` / `.env.bak*`
- [ ] 历史被重写时已记录旧 `origin/main` 并使用 `--force-with-lease`
- [ ] 公开仓 `LICENSE`、`README`、`docs/` 可匿名访问
- [ ] 公开仓默认分支为 `main`

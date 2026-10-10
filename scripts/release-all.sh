#!/usr/bin/env bash
# CenkorProcess 版本发布：递增根 VERSION（vMAJOR.MINOR.PATCH）→ git 提交 + 打 tag → 可选推送。
#
# 用法：
#   bash scripts/release-all.sh [major|minor|patch] [--dry-run] [--no-push]
#   默认粒度 patch；默认提交并推送。
set -euo pipefail
cd "$(dirname "$0")/.."

BUMP="patch"; DRY=0; PUSH=1
for a in "$@"; do
  case "$a" in
    major|minor|patch) BUMP="$a" ;;
    --dry-run) DRY=1 ;;
    --no-push) PUSH=0 ;;
    *) echo "未知参数: $a"; exit 2 ;;
  esac
done

[ -f VERSION ] || { echo "缺少 VERSION 文件"; exit 1; }
CUR="$(tr -d '[:space:]' < VERSION)"            # 形如 v0.1.0
[[ "$CUR" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]] || { echo "VERSION 格式应为 vMAJOR.MINOR.PATCH，当前: $CUR"; exit 1; }
M=${BASH_REMATCH[1]}; N=${BASH_REMATCH[2]}; P=${BASH_REMATCH[3]}
case "$BUMP" in
  major) M=$((M+1)); N=0; P=0 ;;
  minor) N=$((N+1)); P=0 ;;
  patch) P=$((P+1)) ;;
esac
NEW="v${M}.${N}.${P}"

echo "版本：$CUR → $NEW (bump=$BUMP)"
if [ "$DRY" = "1" ]; then echo "[dry-run] 不写入、不提交。"; exit 0; fi

echo "$NEW" > VERSION
git add VERSION
git commit -m "chore(release): bump version to $NEW"
git tag -a "$NEW" -m "CenkorProcess $NEW"
echo "已提交并打 tag：$NEW"
if [ "$PUSH" = "1" ]; then
  BR="$(git rev-parse --abbrev-ref HEAD)"
  git push origin "$BR" && git push origin "$NEW" && echo "已推送到 origin/$BR + tag $NEW"
else
  echo "[--no-push] 跳过推送。稍后手动：git push origin $(git rev-parse --abbrev-ref HEAD) && git push origin $NEW"
fi

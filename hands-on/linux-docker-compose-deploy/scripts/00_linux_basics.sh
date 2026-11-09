#!/usr/bin/env bash
# 阶段 00：Linux 基础操作复刻（对应预习1 day04）
# 覆盖：文件操作 / 权限 / 软硬链接 / 用户 / 压缩解压 / 服务 / 进程 / vim
set -uo pipefail

WORK=/opt/lab/stage00
rm -rf "$WORK"; mkdir -p "$WORK"; cd "$WORK"

hr() { echo; echo "===== $* ====="; }

hr "0 环境信息"
uname -a
head -2 /etc/os-release
echo "current user: $(id -un) uid=$(id -u)"

hr "1.1 文件操作 cat / tail / grep"
printf 'line1\nline2\nline3\n' > lqz.txt
echo "--- cat lqz.txt";      cat lqz.txt
echo "--- tail -n 2 lqz.txt"; tail -n 2 lqz.txt
echo "--- grep line2 lqz.txt"; grep 'line2' lqz.txt
echo "--- grep -c . lqz.txt";  grep -c . lqz.txt

hr "1.2 下载 wget / curl"
echo "--- curl -sI"; curl -sI https://mirrors.tuna.tsinghua.edu.cn | head -1
echo "--- wget 下载小文件"; wget -q -O sha.txt https://mirrors.tuna.tsinghua.edu.cn/ubuntu-cdimage/ubuntu-base/releases/24.04/release/SHA256SUMS && wc -l sha.txt

hr "1.3 文件属性 10 位"
ls -l lqz.txt
stat -c 'mode=%a owner=%U group=%G size=%s' lqz.txt

hr "2 权限 chmod / umask / chown"
touch perm.txt; chmod 640 perm.txt
ls -l perm.txt
echo "umask=$(umask)"
mkdir -p shared && chmod 750 shared && ls -ld shared

hr "3 软硬链接"
echo hello > origin.txt
ln origin.txt hard.txt
ln -s origin.txt soft.txt
echo "--- inode 与链接数"; ls -li origin.txt hard.txt soft.txt
echo "修改源文件 >> origin.txt"
echo "modify-by-origin" >> origin.txt
echo "--- hard.txt 内容"; cat hard.txt
echo "--- soft.txt 内容"; cat soft.txt
rm -f origin.txt
echo "--- 删除源文件后 hard.txt 仍可读"; cat hard.txt
echo "--- 删除源文件后 soft.txt 变成断链"; cat soft.txt 2>&1 || echo "readlink soft.txt -> $(readlink soft.txt) (dangling)"

hr "4 用户与属主"
useradd -m -s /bin/bash luffy 2>/dev/null || true
id luffy
chown luffy:luffy perm.txt
ls -l perm.txt
chown root:root perm.txt

hr "5 压缩解压 tar"
tar czf demo.tar.gz lqz.txt perm.txt
echo "--- 查看包内"; tar tzf demo.tar.gz
mkdir -p extract && tar xzf demo.tar.gz -C extract && echo "--- 解压结果"; ls extract

hr "6 系统服务 systemctl"
systemctl is-active docker
systemctl status docker --no-pager -n 3 | head -8

hr "7 进程管理 ps / pgrep"
ps aux | grep '[d]ockerd' | head -2
echo "dockerd pid: $(pgrep -x dockerd | head -1)"

hr "8 vim 非交互验证"
vim -es -c 'normal ihello from vim' -c 'wq' vim_demo.txt >/dev/null 2>&1
cat vim_demo.txt

hr "9 Docker 版本（为阶段01准备）"
docker version --format 'client={{.Client.Version}} server={{.Server.Version}}'

hr "DONE stage00"

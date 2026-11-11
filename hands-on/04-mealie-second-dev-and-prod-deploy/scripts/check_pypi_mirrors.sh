#!/usr/bin/env bash
for u in \
  https://pypi.tuna.tsinghua.edu.cn/simple/uv/ \
  https://mirrors.aliyun.com/pypi/simple/uv/ \
  https://mirrors.cloud.tencent.com/pypi/simple/uv/ \
  https://pypi.org/simple/uv/; do
  printf '== %s\n' "$u"
  curl -o /dev/null -s -w 'code=%{http_code} time=%{time_total}s\n' --max-time 20 "$u" || echo "curl failed"
done

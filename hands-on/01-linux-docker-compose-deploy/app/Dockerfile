# 访问计数应用镜像：Flask + redis
FROM python:3.12-slim

LABEL maintainer="luffy-lab"

# 工作目录不存在会自动创建，后续命令都在该目录下执行
WORKDIR /app

# 先拷依赖再安装：依赖不变时可复用这一层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 业务代码单独一层，改代码只重建最后一层
COPY app.py .

# 运行时环境变量，可被 docker run -e 覆盖
ENV REDIS_HOST=redis \
    REDIS_PORT=6379

EXPOSE 5000

# 容器启动命令
CMD ["python", "app.py"]

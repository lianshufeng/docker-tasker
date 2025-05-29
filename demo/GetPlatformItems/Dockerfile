FROM selenium/standalone-chrome:134.0-20250525


USER 0

# 手动创建 apt 临时目录，解决权限错误
RUN mkdir -p /var/lib/apt/lists/partial && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        locales \
        fonts-wqy-zenhei \
        fonts-wqy-microhei \
        python3 \
        python3-pip && \
    locale-gen zh_CN.UTF-8 && \
    update-locale LANG=zh_CN.UTF-8 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*



# 设置系统语言为中文
ENV LANG=zh_CN.UTF-8
ENV LANGUAGE=zh_CN:zh
ENV LC_ALL=zh_CN.UTF-8

# 安装 Python3 和 pip（基础环境）
RUN apt-get install -y python3 python3-pip
RUN if [ ! -e /usr/bin/python ]; then ln -s /usr/bin/python3 /usr/bin/python; fi

COPY ./ /opt/app
WORKDIR /opt/app

# 安装你脚本需要的 Python 依赖（可选）
# COPY requirements.txt .
RUN pip3 install -r requirements.txt

# 默认执行你的 Python 脚本
CMD ["python3", "main.py"]

FROM selenium/standalone-chrome:138.0-20250717

USER 0


# 安装 ffmpeg 和 依赖
RUN mkdir -p /var/lib/apt/lists/partial && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        gcc \
        locales \
        fonts-wqy-zenhei \
        fonts-wqy-microhei \
        python3 \
        python3-dev \
        x11-apps \
        python3-tk \
        python3-dev \
        gnome-screenshot\
        python3-pip && \
    locale-gen zh_CN.UTF-8 && \
    update-locale LANG=zh_CN.UTF-8 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*



# 不要设置 VNC 密码
ENV VNC_NO_PASSWORD=1

# 设置系统语言为中文
ENV LANG=zh_CN.UTF-8
ENV LANGUAGE=zh_CN:zh
ENV LC_ALL=zh_CN.UTF-8

# 软链python
RUN if [ ! -e /usr/bin/python ]; then ln -s /usr/bin/python3 /usr/bin/python; fi

COPY ./ /opt/app
WORKDIR /opt/app

# 安装你脚本需要的 Python 依赖（可选）
# COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt


# 在 wait 前插入 exec "$@"，注意处理多行插入 （延迟5秒）
RUN sed -i '/wait \${SUPERVISOR_PID}/i sleep 5\nexec "$@"' /opt/bin/entry_point.sh

# 保留原 ENTRYPOINT，注入执行 CMD 的能力
ENTRYPOINT ["/opt/bin/entry_point.sh"]
CMD [""]

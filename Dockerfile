FROM python:3.9-slim
WORKDIR /app
COPY . /app
RUN apt-get update && \
    apt-get install -y fonts-noto-cjk && \
    rm -rf /var/lib/apt/lists/*
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
RUN pip install --no-cache-dir streamlit requests schedule -i https://pypi.tuna.tsinghua.edu.cn/simple
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
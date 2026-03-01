
<img width="1911" height="822" alt="01" src="https://github.com/user-attachments/assets/deef2dd2-1a65-400c-9f2a-00f6e405891e" />
<img width="1918" height="911" alt="04" src="https://github.com/user-attachments/assets/19510e0c-891b-4808-a6d6-e081432f5a30" />




这是一个专门为 Emby 管理员设计的用户有效期管理工具。
## 🚀 极简部署 (Docker Compose)
👨‍💻 作者:靓仔东 💖 特别感谢: 安卓电视AppleTv群 🐳 Docker 镜像: liangzaidong/yangemby-tools:latest
复制以下内容到你的 `docker-compose.yml`，修改变量后运行即可：

```yaml
version: '3.8'
services:
  emby-manager:
    image: liangzaidong/yangemby-tools:latest
    container_name: yangemby-tools
    restart: always
    network_mode: bridge
    ports:
      - "8055:8501" 
    volumes:
      - "/volume1/docker/yangemby/data:/app/data" # 这里改写为你存放数据的路径
    environment:
      - TZ=Asia/Shanghai
      - EMBY_URL=http://你的IP:8096        # 填入你的 Emby 地址
      - EMBY_API_KEY=你的API密钥           # 填入你的 API Key
      - ADMIN_USERNAME=admin              # 网页登录账号
      - ADMIN_PASSWORD=admin              # 网页登录密码

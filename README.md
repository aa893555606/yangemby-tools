# 🛠️ yangemby-tools (东子版)

这是一个专门为 Emby 管理员设计的用户有效期管理工具。

---

## 🚀 极简部署 (Docker Compose)

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
-------------------------------------------------------------------------------
👨‍💻 作者
Power by 靓仔东
Docker 镜像地址: liangzaidong/yangemby-tools:latest
感谢安卓电视AppleTv群

<img width="2220" height="1125" alt="ScreenShot_2026-02-27_233852_001" src="https://github.com/user-attachments/assets/863defe7-a7c7-47cf-b947-e20def33075e" />
<img width="2232" height="1115" alt="ScreenShot_2026-02-27_233905_148" src="https://github.com/user-attachments/assets/ab2a8df8-8ccd-4bd8-9751-a440d9073dd7" />
<img width="2235" height="1155" alt="ScreenShot_2026-02-27_233737_481" src="https://github.com/user-attachments/assets/ed5d80eb-7ae9-413f-8855-ea72ce0b56e4" />



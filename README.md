# BT 搜索 API

使用 **FastAPI** + **MongoDB** 封装的 BT 搜索接口，默认暴露 `/bt/api` 与 `/api/search` 两条 API：

- `/bt/api`：与 MongoDB 中的多张集合匹配番号或标题。
- `/api/search`：在抓取 AVBase 演员信息的同时返回 BT 搜索结果。

所有行为均通过环境变量配置，推荐直接使用提供的 Docker 镜像部署。

## 环境变量

| 变量名         | 默认值                                                    | 说明                                                   |
| -------------- | --------------------------------------------------------- | ------------------------------------------------------ |
| `API_HOST`     | `0.0.0.0`                                                 | Uvicorn 监听地址。                                     |
| `API_PORT`     | `10000`                                                   | 服务端口（示例命令会覆盖为 `10005`）。                 |
| `BASE_URL`     | `/bt/api`                                                 | API 对外路径，若提供完整 URL 将直接用于日志展示。     |
| `DB_URL`       | `mongodb://crawler:crawler_secure_password@192.168.5.5:27017/sehuatang` | MongoDB 连接串，需包含账号、密码与数据库。             |
| `DB_NAME`      | `sehuatang`                                               | MongoDB 数据库名。                                     |
| `SEARCH_TABLES`| `4k_video,...,vegan_with_mosaic`                          | 逗号分隔的集合列表。                                   |
| `PAGE_SIZE`    | `20`                                                      | 单次查询的逻辑页大小（目前聚合后直接全部返回）。       |
| `PUBLIC_HOST`  | 自动检测                                                  | 当 `BASE_URL` 仅为路径时，用于拼接日志里的访问地址。   |

> 如果 `BASE_URL` 只写路径（推荐），启动日志会根据 `PUBLIC_HOST`（或自动检测到的 IP）与 `API_PORT` 拼出完整示例地址。

## 快速部署

服务器只需要安装 Docker，然后直接运行下面的命令即可拉取并启动镜像（端口、数据库地址等均可按需修改）：

```bash
docker run -d \
  --restart always \
  -p 10005:10005 \
  -e API_PORT="10005" \
  -e BASE_URL="/bt/api" \
  -e DB_URL="mongodb://crawler:crawler_secure_password@192.168.5.5:27017/sehuatang" \
  -e DB_NAME="sehuatang" \
  -e SEARCH_TABLES="4k_video,anime_originate,asia_codeless_originate,asia_mosaic_originate,domestic_original,hd_chinese_subtitles,three_levels_photo,vegan_with_mosaic" \
  -e PAGE_SIZE="20" \
  --name bt-api \
  shutu736/bt-api
```

容器启动后即可访问 `http://<服务器IP>:10005/bt/api?keyword=SNIS&page=1` 或 `http://<服务器IP>:10005/api/search?keyword=白上` 获取数据。

## 接口返回说明

- `/bt/api`：返回 `{"total": 总数, "data": [...]}`，其中 `data` 为 BT 种子列表（包含 `title`、`download_url` 等字段）。
- `/api/search`：返回 `{"code": 200, "actors": ["演员1", ...], "torrents": [...]}`。当 AVBase 或 MongoDB 查询失败时，`code` 会变为 `502/500`，并附带错误信息。

日志与注释均为中文，方便排查问题。如果需要自定义更多行为，可在运行容器时继续追加 `-e` 覆盖环境变量。***

# BT 搜索 API

使用 **FastAPI** + **MongoDB** 封装的 BT 搜索接口，同时支持 `GET`/`POST` 访问 `http://<host>:10005/bt/api`（示例）。项目所有行为都依赖环境变量配置，可直接打包成 Docker 镜像部署。

## 运行依赖

- Python 3.11+
- MongoDB（已存在 4k_video 等集合）
- 访问 MongoDB 的网络权限

## 环境变量

| 变量名          | 默认值                                                     | 说明                                               |
| --------------- | ---------------------------------------------------------- | -------------------------------------------------- |
| `API_HOST`      | `0.0.0.0`                                                  | Uvicorn 监听地址（不填默认 0.0.0.0）               |
| `API_PORT`      | `10000`                                                    | 服务端口（示例中会覆盖为 10005）                   |
| `BASE_URL`      | `/bt/api`                                                  | 可填写完整 URL，或仅填路径（默认 `/bt/api`）       |
| `DB_URL`        | `mongodb://<user>:<password>@<mongo_host>:27017/<db_name>` | MongoDB 连接串模板                                 |
| `DB_NAME`       | `sehuatang`                                                | 库名                                               |
| `SEARCH_TABLES` | `4k_video,...,vegan_with_mosaic`                           | 以逗号分隔的集合列表                               |
| `PAGE_SIZE`     | `20`                                                       | 单页返回条数                                       |
| `PUBLIC_HOST`   | `自动检测`                                                 | 当 `BASE_URL` 是路径时，用于日志拼接的对外 IP/域名 |

> 如果 `BASE_URL` 传入路径（推荐），启动日志会根据 `PUBLIC_HOST`（或自动检测 IP）与 `API_PORT` 动态拼接完整地址。

所有变量都可以通过 Docker `-e` 或 `.env` 文件覆盖。

## 本地运行

```bash
# Windows PowerShell
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
$env:API_PORT = "10005"
$env:BASE_URL = "/bt/api"
uvicorn app.main:app --host 0.0.0.0 --port 10005

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
API_PORT=10005 BASE_URL="/bt/api" uvicorn app.main:app --host 0.0.0.0 --port 10005
```

启动后访问 `http://localhost:10005/bt/api?keyword=jav&page=1` 即可。

## Docker

```bash
docker build -t bt-api .
docker run -d \
  --restart always \
  -p 10005:10005 \
  -e API_PORT="10005" \
  -e BASE_URL="/bt/api" \
  -e DB_URL="mongodb://<user>:<password>@<mongo_host>:27017/<db_name>" \
  -e DB_NAME="<db_name>" \
  -e SEARCH_TABLES="4k_video,anime_originate,asia_codeless_originate,asia_mosaic_originate,domestic_original,hd_chinese_subtitles,three_levels_photo,vegan_with_mosaic" \
  -e PAGE_SIZE="20" \
  --name bt-api \
  bt-api
```

需要修改集合或页大小时，继续通过 `-e` 添加对应环境变量；若部署在公网，可额外传入 `PUBLIC_HOST=<域名或 IP>` 让日志展示正确的访问地址。

## 接口约定

### 请求

- `GET /bt/api?keyword=jav&page=1`（也支持 `query` 参数：`/bt/api?query=jav`）
- `POST /bt/api`（可发送 JSON body，或通过 query string 传入 `keyword/query`/`page`）

```json
{
  "keyword": "jav",
  "page": 1
}
```

> 提示：POST 请求如果不方便携带 JSON，可改用 `keyword` / `query` / `page` 这三个 query 参数，服务会自动回落。

### 响应

```json
{
  "total": 1,
  "data": [
    {
      "id": 1001,
      "site": "BT",
      "size_mb": 0.0,
      "seeders": 0,
      "title": "AAA-123 高清合集",
      "chinese": true,
      "uc": false,
      "uhd": false,
      "free": true,
      "download_url": "magnet:?..."
    }
  ]
  ]
}
```

- `id` 直接取集合中的 `id`
- `site` 永远返回 `BT`
- `title` 固定为 `number + 空格 + title`
- `chinese` 仅 `hd_chinese_subtitles` 集合返回 `true`
- `size_mb`、`seeders` 固定为 `0`
- `download_url` 取文档字段 `magnet`
- `total` 表示本次匹配到的总条数（暂不分页，全部返回）

所有日志默认为中文，方便排查。

# BT 搜索 API

使用 **FastAPI** + **MongoDB** 封装的 BT 搜索接口，同时支持 `GET`/`POST` 访问 `http://192.168.5.5:10000/bt/api`。项目所有行为都依赖环境变量配置，可直接打包成 Docker 镜像部署。

## 运行依赖

- Python 3.11+
- MongoDB（已存在 4k_video 等集合）
- 访问 MongoDB 的网络权限

## 环境变量

| 变量名 | 默认值 | 说明 |
| --- | --- | --- |
| `API_HOST` | `0.0.0.0` | Uvicorn 监听地址 |
| `API_PORT` | `10000` | 服务端口 |
| `BASE_URL` | `http://192.168.5.5:10000/bt/api` | 仅用于日志提示 |
| `DB_URL` | `mongodb://crawler:crawler_secure_password@192.168.5.5:27017/sehuatang` | MongoDB 连接串 |
| `DB_NAME` | `sehuatang` | 库名 |
| `SEARCH_TABLES` | `4k_video,...,vegan_with_mosaic` | 以逗号分隔的集合列表 |
| `PAGE_SIZE` | `20` | 单页返回条数 |

所有变量都可以通过 Docker `-e` 或 `.env` 文件覆盖。

## 本地运行

```bash
python -m venv .venv
.venv/Scripts/activate  # PowerShell
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 10000
```

启动后访问 `http://localhost:10000/bt/api?keyword=jav&page=1` 即可。

## Docker

```bash
docker build -t bt-api .
docker run --rm -p 10000:10000 \
  -e DB_URL="mongodb://crawler:***@192.168.5.5:27017/sehuatang" \
  bt-api
```

如果需要修改集合或页大小，继续添加对应环境变量。

## 接口约定

### 请求

- `GET /bt/api?keyword=jav&page=1`
- `POST /bt/api`

```json
{
  "keyword": "jav",
  "page": 1
}
```

### 响应

```json
{
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
}
```

- `id` 直接取集合中的 `id`
- `site` 永远返回 `BT`
- `title` 固定为 `number + 空格 + title`
- `chinese` 仅 `hd_chinese_subtitles` 集合返回 `true`
- `size_mb`、`seeders` 固定为 `0`
- `download_url` 取文档字段 `magnet`

所有日志默认为中文，方便排查。

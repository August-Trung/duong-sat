# Đường Sắt Biên Hòa

Hệ thống theo dõi điểm giao cắt đường sắt khu vực Biên Hòa, gồm backend FastAPI, frontend Vue và pipeline crawl dữ liệu.

## Nguyên tắc dữ liệu hiện tại

- Dữ liệu fake hiện có vẫn được giữ nguyên để UI và API tiếp tục chạy ổn định.
- Dữ liệu thật mới được crawl theo cơ chế `staging`: xuất ra file preview trước, chỉ import vào DB khi đã kiểm tra.
- Mọi file kỹ thuật mới đều dùng UTF-8.

## Thành phần chính

- Backend: `src/railway_crawler/`
- Frontend: `frontend/src/`
- CSDL chạy local: `data/railway.db`
- Dữ liệu vector thật: `vietnam.gpkg`
- Dữ liệu staging thật: `data/staging/`

## Cài đặt

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

### Frontend

```powershell
cd .\frontend
npm install
```

## Chạy hệ thống

### Backend

```powershell
$env:PYTHONPATH = "D:\Study\Projects\DuongSat\src"
.\.venv\Scripts\python -m uvicorn railway_crawler.api:app --host 127.0.0.1 --port 8000
```

Hoặc dùng script:

```powershell
.\start-backend.ps1
```

Script này sẽ tự đọc DB đang active từ `data\active-db.txt`. Nếu file này không có, backend sẽ dùng `data\railway.db`.
Nếu có file `.env.local` ở root project, script cũng sẽ nạp các biến môi trường local trước khi chạy backend.

### Frontend

```powershell
cd .\frontend
npm run dev
```

Frontend đã tách rõ 2 môi trường:

- Local dev: [frontend/.env.development](D:/Study/Projects/DuongSat/frontend/.env.development) dùng `VITE_API_BASE_LOCAL=/api`, đi qua Vite proxy sang `127.0.0.1:8000`
- Host/build: [frontend/.env.production](D:/Study/Projects/DuongSat/frontend/.env.production) dùng `VITE_API_BASE_HOST=https://duongsat-api.onrender.com/api`

Không nên để frontend local trỏ thẳng vào API host khi đang kiểm thử dữ liệu local.

## Cấu hình local và host

- Backend local mẫu: [.env.local.example](D:/Study/Projects/DuongSat/.env.local.example)
- Backend host mẫu: [.env.host.example](D:/Study/Projects/DuongSat/.env.host.example)
- Frontend local: [frontend/.env.development](D:/Study/Projects/DuongSat/frontend/.env.development)
- Frontend host: [frontend/.env.production](D:/Study/Projects/DuongSat/frontend/.env.production)

Quy ước nên dùng:

- Làm và kiểm tra dữ liệu trên local với `data/railway.db`
- Khi ổn, chạy [sync-host-db.ps1](D:/Study/Projects/DuongSat/sync-host-db.ps1) để đồng bộ DB local về snapshot `data/railway.db` dùng cho host
- Sau đó commit và push để host deploy cùng đúng DB đó

## Lệnh dữ liệu

Khởi tạo DB:

```powershell
railway-crawler init-db --db .\data\railway.db
```

Seed dữ liệu fake:

```powershell
railway-crawler seed-fake --db .\data\railway.db
```

Crawl lịch tàu thật từ nguồn chính thức:

```powershell
railway-crawler fetch-schedules --db .\data\railway.db --config .\crawler.toml
```

Crawl tin thật:

```powershell
railway-crawler fetch-news --db .\data\railway.db --config .\crawler.toml
```

Xuất ứng viên điểm giao cắt thật từ GPKG ra staging, chưa chạm vào dữ liệu fake:

```powershell
railway-crawler extract-real-crossings --db .\data\railway.db --gpkg .\vietnam.gpkg --out .\data\staging\real_crossing_candidates.json
```

Nếu muốn file CSV để rà soát rồi import:

```powershell
railway-crawler extract-real-crossings --db .\data\railway.db --gpkg .\vietnam.gpkg --out .\data\staging\real_crossing_candidates.csv
```

Suy ra ứng viên sự cố từ tin đã crawl, mặc định chỉ xuất preview:

```powershell
railway-crawler derive-incidents --db .\data\railway.db --config .\crawler.toml --out .\data\staging\incident_candidates.json
```

Chỉ khi đã rà soát xong mới ghi ứng viên sự cố vào DB:

```powershell
railway-crawler derive-incidents --db .\data\railway.db --config .\crawler.toml --out .\data\staging\incident_candidates.json --apply
```

Import ứng viên điểm giao cắt đã kiểm tra vào DB:

```powershell
railway-crawler import-crossings --db .\data\railway.db --csv .\data\staging\real_crossing_candidates.csv
```

Tạo trial DB từ DB hiện tại nhưng thay cụm `crossings` bằng dữ liệu staging:

```powershell
.\prepare-trial-db.ps1
```

Đổi backend sang trial DB:

```powershell
.\use-trial-db.ps1
```

Rollback về DB mặc định:

```powershell
.\rollback-db.ps1
```

Tính lại risk snapshot:

```powershell
railway-crawler compute-risk --db .\data\railway.db
```

## Trạng thái crawler thật

- `fetch-schedules`: lấy giờ tàu thật từ `https://giotaugiave.dsvn.vn/`
- `fetch-news`: lấy tin thật qua Google News RSS theo bộ từ khóa cấu hình
- `derive-incidents`: suy diễn sự cố từ tin thật có match rõ với điểm giao cắt
- `extract-real-crossings`: suy ra ứng viên giao cắt thật từ giao điểm hình học giữa đường bộ và đường sắt trong OSM/GPKG

## Lưu ý quan trọng

- `extract-real-crossings` hiện tạo danh sách ứng viên, không tự khẳng định đó là bản ghi đã xác minh hiện trường.
- `derive-incidents` mặc định không ghi DB để tránh làm bẩn dữ liệu vận hành.
- Khi chưa crawl và kiểm chứng đủ dữ liệu thật, hệ thống vẫn tiếp tục dùng dữ liệu fake hiện tại cho UI.

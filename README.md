# Đường Sắt Biên Hòa

Hệ thống theo dõi điểm giao nhau đường sắt khu vực Biên Hòa, gồm backend FastAPI, frontend Vue và scene 3D dựng bằng Three.js từ dữ liệu OSM thật.

## Thành phần chính

- Backend: `src/railway_crawler/`
- Frontend: `frontend/src/`
- Cơ sở dữ liệu: `data/railway.db`
- OSM vector thật: `vietnam.gpkg`
- DEM đang dùng:
  - `n10_e106_1arc_v3.tif`
  - `n11_e106_1arc_v3.tif`
- Asset 3D thật:
  - `frontend/public/assets/scene3d/transmission_tower.glb`
  - `frontend/public/assets/scene3d/nature_kit/`

## Cài đặt

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

Nếu backend vừa thêm dependency mới:

```powershell
.\.venv\Scripts\python -m pip install -e .
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

### Frontend

```powershell
cd .\frontend
npm run dev
```

## Lệnh quan trọng

Khởi tạo DB:

```powershell
railway-crawler init-db --db .\data\railway.db
```

Seed dữ liệu mẫu:

```powershell
railway-crawler seed-fake --db .\data\railway.db
```

Export scene 3D từ OSM thật và DEM:

```powershell
railway-crawler export-scene3d --db .\data\railway.db --gpkg .\vietnam.gpkg --dem .\n10_e106_1arc_v3.tif .\n11_e106_1arc_v3.tif --out .\generated\scene3d
```

## Scene 3D hiện tại

- Dữ liệu đường, đường sắt, building, landuse, water lấy từ `vietnam.gpkg`
- Terrain lấy từ 2 tile `SRTM 1 Arc-Second Global` dạng `GeoTIFF`
- Exporter đã hỗ trợ:
  - `.json`
  - `.asc`
  - `.grd`
  - `.tif`
  - `.tiff`
- Có cache subset GPKG tại `generated/scene3d/gpkg_subset_cache.sqlite`

## Trạng thái renderer 3D

- Tile streaming theo camera
- LOD gần, trung bình, xa
- Giữ chuột trái để di chuyển, chuột phải để xoay
- Đường luôn render dạng mặt đường phẳng nhiều lớp thay vì tụt hết về line ở zoom xa
- Tên đường thật được in lặp theo quãng trực tiếp trên mặt đường ở các tuyến có tên hoặc mã đường
- Building tách mái và tường
- Nền đất và landuse xanh dùng texture ảnh thật từ bộ `Nature Kit`
- Cây dùng asset thật ở gần, sprite nhẹ hơn ở khoảng trung bình để tránh đơ
- Đã nạp asset trụ điện `.glb`, nhưng scene export hiện chưa có `powerlines` thật nên chưa có gì để dựng trụ điện trên bản đồ

## Giới hạn hiện tại

- DEM mới phủ `106E`, chưa phủ thêm phần `107E`
- Scene export hiện có `powerlines = 0`
- Chunk route 3D vẫn còn lớn
- Nhãn đường hiện bám theo từng đoạn tuyến, chưa uốn cong liên tục theo toàn bộ con đường

## Tài liệu đi kèm

- `docs/HANDOFF.md`
- `docs/RULES.md`
- `docs/BACKLOG.md`
- `docs/SKILLS.md`
- `docs/threejs-3d-architecture.md`

## Quy tắc bắt buộc

- Mọi nội dung hiển thị và tài liệu phải dùng tiếng Việt có dấu, lưu UTF-8
- Sau mỗi đợt làm việc phải cập nhật toàn bộ file `.md` để phản ánh đúng hiện trạng dự án

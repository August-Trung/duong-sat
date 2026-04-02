# Handoff Dự Án

## Mục tiêu

Repo này quản lý dữ liệu điểm giao cắt đường sắt, hiển thị public và admin, đồng thời dựng scene 3D từ dữ liệu OSM thật.

## Điểm vào chính

- Backend API: `src/railway_crawler/api.py`
- CLI: `src/railway_crawler/cli.py`
- Export scene 3D: `src/railway_crawler/scene3d.py`
- Route frontend: `frontend/src/router.js`
- Trang 3D: `frontend/src/pages/PublicThreeScenePage.vue`
- Renderer 3D: `frontend/src/components/Scene3DCanvas.vue`

## Cách chạy nhanh

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

## Dữ liệu hiện có

- DB: `data/railway.db`
- OSM vector thật: `vietnam.gpkg`
- DEM:
  - `n10_e106_1arc_v3.tif`
  - `n11_e106_1arc_v3.tif`
- Asset 3D thật:
  - `frontend/public/assets/scene3d/transmission_tower.glb`
  - `frontend/public/assets/scene3d/nature_kit/`

## Lệnh export scene 3D

```powershell
railway-crawler export-scene3d --db .\data\railway.db --gpkg .\vietnam.gpkg --dem .\n10_e106_1arc_v3.tif .\n11_e106_1arc_v3.tif --out .\generated\scene3d
```

## Trạng thái kỹ thuật hiện tại

- Exporter đã đọc được nhiều GeoTIFF DEM cùng lúc
- Renderer 3D đã có:
  - tile streaming
  - LOD
  - picking object
  - chuột trái để pan
  - chuột phải để xoay
  - đường dạng ribbon phẳng ở nhiều mức zoom
  - tên đường thật in lặp trực tiếp trên mặt đường
  - building tách mái và tường
  - landuse và terrain dùng texture thật
  - cây dùng asset thật ở gần và sprite nhẹ ở trung bình
- Asset trụ điện thật đã nạp qua `GLTFLoader`

## Điều cần nhớ

- Manifest hiện tại có `powerlines = 0`
- Vì chưa có dữ liệu tuyến điện thật trong scene export, trụ điện sẽ chưa xuất hiện trên bản đồ dù model đã sẵn sàng
- Nếu muốn thấy trụ điện, cần bổ sung nguồn vector có `power=line` hoặc tile export có powerline thực

## Việc cần kiểm tra đầu tiên

- `GET /api/health`
- `GET /api/scene3d/manifest`
- Trang `http://localhost:5173/scene-3d`
- Kiểm tra:
  - pan bằng chuột trái
  - xoay bằng chuột phải
  - tên đường bám mặt đường
  - cây còn hiện khi di chuyển camera
  - mặt đường còn giữ dạng phẳng khi zoom xa

## Bước tiếp theo hợp lý

1. Bổ sung DEM `107E`
2. Bổ sung dữ liệu powerline thật
3. Cải thiện label cong theo toàn tuyến
4. Tối ưu tiếp chunk route 3D

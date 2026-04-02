# Năng Lực Hiện Có

## Backend

- FastAPI cho public và admin API
- SQLite cho dữ liệu nghiệp vụ
- CLI cho init DB, import, crawl, compute risk, seed và export scene 3D

## Frontend

- Vue 3 + Vite
- Leaflet cho bản đồ 2D
- Three.js cho scene 3D

## Scene 3D

- Đọc OSM thật từ `vietnam.gpkg`
- Đọc nhiều tile DEM GeoTIFF
- Tile streaming
- LOD
- Picking object
- Pan bằng chuột trái, xoay bằng chuột phải
- Đường ribbon nhiều lớp và nhãn tên đường thật
- Building tách mái và tường
- Texture nền thật từ bộ `Nature Kit`
- Cây thật qua `OBJLoader + MTLLoader`
- Trụ điện `.glb` thật qua `GLTFLoader`

## Khoảng trống còn thiếu

- Dữ liệu powerline thật trong scene export
- DEM phủ đủ mép `107E`
- Label cong theo toàn tuyến
- Test tự động cho exporter và renderer

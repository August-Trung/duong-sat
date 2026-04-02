# Kiến Trúc Scene 3D Three.js

## Mục tiêu

Tạo scene 3D dùng dữ liệu thật, có thể mở rộng dần tới mức gần với trải nghiệm kiểu F4Map.

## Pipeline dữ liệu

### Nguồn

- OSM vector thật: `vietnam.gpkg`
- DEM hiện tại:
  - `n10_e106_1arc_v3.tif`
  - `n11_e106_1arc_v3.tif`
- DB nghiệp vụ: `data/railway.db`

### Exporter

File chính: `src/railway_crawler/scene3d.py`

Exporter hiện hỗ trợ:

- OSM XML
- GeoPackage thật
- DEM:
  - `.json`
  - `.asc`
  - `.grd`
  - `.tif`
  - `.tiff`

### Kết quả export

- `generated/scene3d/manifest.json`
- `generated/scene3d/tiles/*.json`

## Cache

Để tránh quét toàn bộ `vietnam.gpkg` ở mỗi lần export:

- subset được cache tại `generated/scene3d/gpkg_subset_cache.sqlite`
- cache dựa trên:
  - đường dẫn nguồn
  - kích thước file
  - thời gian sửa file
  - bbox scene

## Renderer

File chính: `frontend/src/components/Scene3DCanvas.vue`

### Thành phần hiện có

- Three.js scene
- OrbitControls
- tile streaming theo camera
- LOD gần, trung bình, xa
- picking object
- overlay thông tin object
- `GLTFLoader` cho trụ điện `.glb`
- `OBJLoader + MTLLoader` cho cây từ bộ `Nature Kit`

### Điều khiển hiện tại

- Chuột trái: pan
- Chuột phải: xoay
- Con lăn: zoom

## Lớp dữ liệu đang render

- terrain
- roads
- railways
- buildings
- landuse
- water
- crossings
- powerlines nếu tile export có dữ liệu

## Trạng thái hiển thị hiện tại

### Roads

- Đường dùng ribbon nhiều lớp:
  - outline
  - edge
  - surface
- Đường chính có vạch tim
- Ở zoom xa vẫn giữ mặt đường phẳng thay vì tụt hết về line
- Tên đường thật được đặt lặp theo quãng trực tiếp trên mặt đường

### Buildings

- Building gần và trung bình có tường và mái tách riêng
- Building xa dùng box proxy để nhẹ hơn

### Vegetation

- Terrain và landuse dùng texture ảnh thật từ bộ `Nature Kit`
- Cây gần dùng asset thật
- Cây trung bình dùng sprite nhẹ để không đơ
- Mật độ cây thay đổi theo `landuse.kind`

### Powerlines

- Renderer đã sẵn sàng cho tower `.glb`
- Nếu tile có `powerlines`, tower sẽ được clone từ asset thật
- Hiện scene export vẫn chưa có powerline thật, nên tower chưa xuất hiện

## Hiệu năng

- Tile active bị giới hạn theo khoảng cách camera
- Cache tile theo LRU
- Building bị cắt bớt theo LOD
- Route 3D đã tách chunk riêng

## Giới hạn hiện tại

- DEM mới phủ `106E`, chưa phủ thêm `107E`
- Nguồn vector hiện chưa sinh ra `powerlines` thật cho scene export
- Nhãn đường mới bám theo từng đoạn tuyến, chưa cong liên tục theo hình học đầy đủ của cả tuyến

## Hướng phát triển tiếp

1. Bổ sung DEM `107E`
2. Bổ sung dữ liệu powerline thật
3. Làm label engine cong theo toàn tuyến
4. Tối ưu tiếp số object khi zoom xa

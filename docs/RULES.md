# Quy Tắc Dự Án

## Quy tắc bắt buộc

- Mọi nội dung giao diện, tài liệu và ghi chú kỹ thuật phải dùng tiếng Việt có dấu và lưu đúng UTF-8.
- Sau mỗi lần hoàn thành công việc phải cập nhật toàn bộ file `.md` của dự án để phản ánh đúng hiện trạng.

## Quy tắc backend

- SQLite là nguồn dữ liệu nghiệp vụ chính.
- API public và admin phải tách quyền rõ ràng.
- Mọi thay đổi schema phải cập nhật API và tài liệu liên quan.
- Lệnh CLI cần chạy lại được mà không phá dữ liệu hiện có.

## Quy tắc frontend

- Frontend chỉ thao tác qua API.
- Route public, admin và scene 3D phải tách rõ.
- Không hardcode dữ liệu nghiệp vụ trong UI.

## Quy tắc scene 3D

- Scene 3D là lớp hiển thị, không thay thế dữ liệu nghiệp vụ.
- Nguồn vector thật hiện ưu tiên `vietnam.gpkg`.
- DEM là nguồn terrain riêng, không giả lập từ dữ liệu vector.
- Mỗi lần đổi format manifest, tile hoặc cách render phải cập nhật tài liệu 3D.

## Definition of Done

- Chạy được local
- Build được frontend nếu có sửa frontend
- Export scene 3D được nếu có sửa pipeline 3D
- Tài liệu `.md` đã được cập nhật

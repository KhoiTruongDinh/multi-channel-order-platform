# S01 fixed fixtures — Multi-channel Order Data Platform

Đây là **bộ sample data cố định, chạy kiểm tra được**, chưa phải simulator hoặc
pipeline hoàn chỉnh. Chạy lại với cùng file sẽ kiểm tra cùng tình huống S01.
Chỉ cần **Python 3.10+**, không cần cài package, database, Docker hay tài khoản sàn.

## Chạy lần đầu

Giải nén và mở terminal tại thư mục `s01-fixtures`:

```bash
python verify.py --report verification_report.json
python -m unittest -v test_tools
```

Trên Windows, có thể dùng `py` thay cho `python`. Nếu báo `PASS`, các file đã khớp
những điều kiện kiểm tra offline. **Không có nghĩa pipeline/API server đã chạy**.

## Nên đọc file nào?

| Đọc theo thứ tự | File / thư mục | Ý nghĩa |
|---|---|---|
| 1 | `scenario.json` | Timeline S01, tham số đã duyệt |
| 2 | `responses/internal_web/WEB_R1.json` → `WEB_R2.json` → `WEB_R3.json` | Toàn bộ selected records của 9 bảng website tại từng lần đọc |
| 3 | `responses/ebay_sim/EB_R1.json`, `EB_R2.json`, `EB_F1.json` | Response order list và fulfillment |
| 4 | `responses/etsy_sim/ET_R1.json`, `ET_R2.json` | Hai lần đọc cùng một receipt version |
| 5 | `webhooks/` | Raw body bytes, headers có chữ ký thật bằng test key, và 3 lần delivery |
| 6 | `config/product_mapping.json` | 4 mapping độc lập, không chứa order ID |
| 7 | `expected/` | Đáp án kiểm thử; pipeline tương lai **không được đọc** |

`requests/` ghi request/context tương ứng. `acquisitions.json` ghi 8 acquisition
đã lên lịch: 3 website, 2 eBay order, 1 fulfillment, 2 Etsy receipt. Nó là playback
manifest, không phải bảng nguồn hay code ingestion. `interface_examples/` có
detail/list/empty envelopes để dựng interface; không tự thêm các ví dụ này vào
timeline quan sát. S01 có 1 eBay order nên **chưa test được phân trang nhiều trang**.

## Phân biệt state nguồn và snapshot đã quan sát

`source_states/` chứa các trạng thái để simulator sau này tiến theo đồng hồ:
website 09:00/09:01/09:10/09:14; eBay 09:02/09:12; Etsy 09:04/09:05.
Một số trạng thái **không bao giờ được pipeline đọc trong S01**. Ví dụ Etsy09:04
đã paid nhưng chưa ship: tồn tại ở nguồn mô phỏng, không được thêm vào observed
history. Pipeline thật sẽ chỉ truy cập API/webhook; không đọc backing source state
hay file expected để lấy đáp án.

## Kết quả đã thống nhất

- 3 current orders; 4 current lines; 6 ordered units; gross merchandise USD124.
- 6 **order** snapshot versions: website3, eBay2, Etsy1.
- 8 archived **line rows** bên trong 6 parent snapshots (eBay mỗi snapshot có2line).
  Đây không phải 8 đơn hoặc 8 lần vendor cập nhật; line archive ghi theo parent snapshot.
- 2 logical webhook messages / 3 delivery attempts; không thêm history cho ET_R2.
- Website cuối S01 PAID + CANCELED, chưa có refund thành công.
- eBay PARTIALLY_SHIPPED nhờ order + dated fulfillment; không có FUL002.
- Etsy SHIPPED, cancellation UNKNOWN theo quy tắc đã duyệt; không suy ra DELIVERED.
- `snapshot_evidence.json` liên kết EB_H2 với cả EB_R2 và EB_F1.

Tiền website trong JSON dùng decimal strings để tránh binary float khi chuyển file;
schema website logic vẫn là exact decimal(18,2). eBay giữ decimal string; Etsy giữ
integer amount/divisor. Identifier nguồn Etsy là integer; ID trong output chung là string.
eBay tax-free S01 **bỏ container tax**, không ghi tax giả bằng0.

## Webhook: kiểm tra offline và chạy thử local về sau

Các body được lưu **không thêm newline**; không format lại trước khi xác thực.
Headers ký chính xác body bằng HMAC-SHA256 với public local-test key trong
`fixture_tools.py`. Prefix `v1,` được dùng theo selected local signing contract;
chưa được kiểm chứng bằng callback thật của Etsy. Đây không phải production key.

Các headers trong `webhooks/` dùng đồng hồ fixture ngày17Oct2026. `verify.py` kiểm
tra chữ ký và freshness bằng received_at được inject từ cùng đồng hồ. Không đem
headers cũ gửi tới receiver dùng giờ hiện tại rồi bỏ kiểm tra timeout.

Khi cần playback thật bằng giờ hiện tại:

```bash
python render_webhooks.py --output-dir runtime_webhooks
```

Script dịch các mốc ký/nhận sang giờ hiện tại, tạo `schedule.json`, không tự gửi
request. D1 lập lịch ngay, D2 sau60giây, D3 sau120giây. Đọc lịch và gửi đúng thời
điểm khi receiver đã có. Body/IDs cố định; timestamp/chữ ký runtime sẽ đổi.
Giá trị receipt created/updated vẫn là business time của S01.

## Những gì đã được kiểm tra

`verify.py` kiểm tra checksum; cấu trúc/type selected fields; FK website;
công thức tiền; product mapping; evidence gửi hàng; source-derived order/line facts;
6 observed versions; current states; raw-byte signature/freshness; cardinality;
snapshot evidence; và không tự suy ra refund/delivered.

`test_tools.py` kiểm tra utilities với missing/null, aliases xung đột, reordered
lines, duplicate IDs, changed quantity, chữ ký sai/body thay đổi, stale timestamp,
divisor0 và mapping conflict/wrong account. Đây là utility/fixture tests, **không**
phải test durable inbox, database transactions, retry worker, race condition,
restart, vendor integration hay performance. Những phần đó chưa triển khai.

## Khi sửa fixture

`references/review_snapshot.json` là bản trích từ sheet đã review, dùng cho tác giả
fixtures và golden answers; không phải nguồn dữ liệu production.
Sau khi cố ý sửa builder hoặc snapshot, chạy:

```bash
python build_fixtures.py
python verify.py --report verification_report.json
python -m unittest -v test_tools
```

Builder ghi lại generated fixtures theo S01 và cập nhật checksum. Không dùng nó
để sửa golden answer cho khớp một pipeline đang sai. Expected data phải được
review độc lập. Utility fingerprint nhận **business object**; metadata fetched_at,
run_id nằm ngoài object. Source timestamp là ordering evidence riêng, không phải
timestamp mới hơn luôn đồng nghĩa chỉ có 1 version trong cùng giây.

## Phạm vi / nguồn tham chiếu

Đây là selected local contract, không phải replica đầy đủ/được chứng nhận của sàn.
Không chứa dữ liệu khách hàng thật. Tên/ID test là synthetic. Không cam kết raw
provider fields ngoài subset, quyền truy cập, quota production, lịch sử đầy đủ,
các nhánh tài chính ngoài S01 hay schema JSON chính thức toàn API.

- eBay OAS: https://developer.ebay.com/api-docs/master/sell/fulfillment/openapi/3/sell_fulfillment_v1_oas3.json
- Etsy OAS: https://www.etsy.com/openapi/generated/oas/3.0.0.json
- Webhooks: https://developer.etsy.com/documentation/essentials/webhooks/
- Project Doc: https://docs.google.com/document/d/13HWKCL8ZnG7ILXDkbBxpQvIyLuVcHpqPGnoPXsVCaJE
- Review Sheet: https://docs.google.com/spreadsheets/d/1KSrluLRO0NMzu7_kLbUNsNXz9O_xgMvzQ9y3ReLTf54/edit

Bước sau: dựng local source interfaces sử dụng fixtures; rồi ingestion và
materialization. Full output database DDL/operational tables sẽ được viết cùng
pipeline; expected JSON ở đây là golden data, không giả vờ là database đã tồn tại.

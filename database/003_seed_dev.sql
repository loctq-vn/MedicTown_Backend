-- =========================================================
-- INITIAL DATA
-- =========================================================

insert into public.product_categories
(id, name, description, sort_order, is_active)
values
('PHARMACEUTICAL', 'Dược phẩm', 'Thuốc phòng bệnh, chẩn đoán, chữa bệnh hoặc điều chỉnh chức năng sinh lý.', 10, true),
('SUPPLEMENT', 'Thực phẩm chức năng', 'Sản phẩm hỗ trợ sức khỏe, không thay thế thuốc chữa bệnh.', 20, true),
('MEDICAL_DEVICE', 'Trang thiết bị và vật tư y tế', 'Vật tư tiêu hao và thiết bị y tế dùng trong gia đình.', 30, true),
('DERMO_COSMETIC', 'Dược mỹ phẩm', 'Sản phẩm chăm sóc, hỗ trợ điều trị các vấn đề da liễu.', 40, true),
('PERSONAL_CARE', 'Chăm sóc cá nhân và vệ sinh', 'Sản phẩm vệ sinh, chăm sóc sức khỏe hàng ngày.', 50, true)
on conflict (id) do update set
  name = excluded.name,
  description = excluded.description,
  sort_order = excluded.sort_order,
  is_active = excluded.is_active;

insert into public.product_subcategories
(id, category_id, name, description, requires_prescription_default, sort_order, is_active)
values
-- Dược phẩm
('OTC', 'PHARMACEUTICAL', 'Thuốc không kê đơn', 'Thuốc có thể mua không cần đơn bác sĩ, dùng cho triệu chứng nhẹ.', false, 10, true),
('RX', 'PHARMACEUTICAL', 'Thuốc kê đơn', 'Thuốc bắt buộc có chỉ định hoặc đơn thuốc của bác sĩ.', true, 20, true),
('HERBAL_MEDICINE', 'PHARMACEUTICAL', 'Thuốc đông y / thuốc dược liệu', 'Thuốc từ dược liệu, thảo dược hoặc y học cổ truyền.', false, 30, true),

-- Thực phẩm chức năng
('VITAMIN_MINERAL', 'SUPPLEMENT', 'Vitamin và khoáng chất', 'Vitamin C, kẽm, canxi, sắt, viên sủi tổng hợp.', false, 10, true),
('ORGAN_SUPPORT', 'SUPPLEMENT', 'Hỗ trợ chức năng', 'Bổ gan, bổ não, men vi sinh, hỗ trợ xương khớp.', false, 20, true),
('BEAUTY_HORMONE', 'SUPPLEMENT', 'Làm đẹp và nội tiết', 'Collagen, viên uống cấp nước, mầm đậu nành.', false, 30, true),

-- Thiết bị / vật tư y tế
('MEDICAL_CONSUMABLE', 'MEDICAL_DEVICE', 'Vật tư tiêu hao', 'Bông, băng gạc, cồn y tế, khẩu trang, găng tay, que thử.', false, 10, true),
('PERSONAL_MONITORING_DEVICE', 'MEDICAL_DEVICE', 'Thiết bị theo dõi cá nhân', 'Máy đo huyết áp, nhiệt kế, máy đo đường huyết, máy xông khí dung.', false, 20, true),

-- Dược mỹ phẩm
('ACNE_SKIN_TREATMENT', 'DERMO_COSMETIC', 'Điều trị mụn và da liễu', 'Kem trị mụn, BHA, Retinol, sản phẩm cho da viêm.', false, 10, true),
('PIGMENTATION_SCAR_TREATMENT', 'DERMO_COSMETIC', 'Nám, sẹo và phục hồi da', 'Kem trị nám, trị sẹo, phục hồi hàng rào bảo vệ da.', false, 20, true),
('SCALP_TREATMENT', 'DERMO_COSMETIC', 'Da đầu và tóc đặc trị', 'Dầu gội trị nấm, gàu, viêm da đầu.', false, 30, true),

-- Chăm sóc cá nhân
('ORAL_CARE', 'PERSONAL_CARE', 'Chăm sóc răng miệng', 'Nước súc miệng, kem đánh răng, sản phẩm chống ê buốt.', false, 10, true),
('FEMININE_HYGIENE', 'PERSONAL_CARE', 'Vệ sinh phụ nữ', 'Dung dịch vệ sinh phụ nữ và sản phẩm chăm sóc vùng kín.', false, 20, true),
('DAILY_HYGIENE', 'PERSONAL_CARE', 'Vệ sinh hàng ngày', 'Xà phòng diệt khuẩn, sản phẩm làm sạch và bảo vệ cơ thể.', false, 30, true),
('BREATH_CARE', 'PERSONAL_CARE', 'Thơm miệng', 'Kẹo ngậm, xịt thơm miệng, sản phẩm hỗ trợ hơi thở.', false, 40, true)
on conflict (id) do update set
  category_id = excluded.category_id,
  name = excluded.name,
  description = excluded.description,
  requires_prescription_default = excluded.requires_prescription_default,
  sort_order = excluded.sort_order,
  is_active = excluded.is_active;
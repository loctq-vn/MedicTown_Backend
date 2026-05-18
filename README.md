# MedicTown Backend

Backend FastAPI trung gian giua ung dung Android va Supabase. Android chi goi API backend, khong can luu `SUPABASE_URL`, `AUTH_URL`, `STORAGE_URL` va `SUPABASE_ANON_KEY` trong app.

## Cau truc

```text
app/
  main.py              # Khoi tao FastAPI app
  config.py            # Doc bien moi truong tu .env
  database.py          # Khoi tao Supabase client
  dependencies.py      # Xac thuc Bearer token va phan quyen
  routers/             # Endpoint Android se goi
  schemas/             # Pydantic request/response models
  services/            # Logic lam viec voi Supabase
```

## Cai dat

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Cau hinh

Sua file `.env`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-or-service-role-key
CORS_ORIGINS=*
```

Neu backend chi doc/ghi qua Row Level Security cua Supabase, co the dung anon key. Neu backend can quyen admin, dung service role key nhung chi luu tren server, khong dua vao Android va khong commit len GitHub.

## Chay server

```bash
uvicorn app.main:app --reload
```

Mac dinh API chay tai:

```text
http://127.0.0.1:8000
```

Tai lieu Swagger:

```text
http://127.0.0.1:8000/docs
```

## API hien co

### Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/google`
- `GET /api/auth/me`

### Users

- `GET /api/users/me`
- `PATCH /api/users/me`
- `POST /api/users/me/avatar`
- Compat cu: `GET /api/users?id=eq.{user_id}`, `PATCH /api/users?id=eq.{user_id}`

### Address

- `GET /api/address`
- `POST /api/address`
- `PATCH /api/address/{address_id}`
- `DELETE /api/address/{address_id}`
- Compat cu: `PATCH /api/address?id=eq.{address_id}`, `DELETE /api/address?id=eq.{address_id}`

### Cart

- `GET /api/cart_items`
- `POST /api/cart_items`
- `PATCH /api/cart_items/{cart_item_id}`
- `DELETE /api/cart_items/{cart_item_id}`
- `DELETE /api/cart_items`
- Compat cu: `PATCH /api/cart_items?id=eq.{cart_item_id}`, `DELETE /api/cart_items?id=in.(id1,id2)`

### Products

- `GET /api/products`
- `GET /api/products?is_featured=true&is_active=true`
- `GET /api/products/featured`
- `GET /api/products/{product_id}`

### Orders

- `POST /api/orders`
- `GET /api/orders`
- `GET /api/orders/{order_id}`
- `POST /api/order_items`

### Payments

- `POST /api/payments`
- `GET /api/payments/{payment_id}`

### Reviews

- `POST /api/reviews`
- `GET /api/reviews?order_item_id={order_item_id}`
- `GET /api/reviews?product_id={product_id}`
- `GET /api/reviews/products/{product_id}`

## Goi tu Android

Sau khi login, backend tra ve `access_token`. Android gui token nay trong moi request can dang nhap:

```text
Authorization: Bearer <access_token>
```

Vi du flow:

1. Android goi `POST /api/auth/login`.
2. Luu `access_token` trong storage an toan cua Android.
3. Goi `GET /api/orders` voi header `Authorization`.

## Mapping tu Retrofit cu

Trong Android, doi `RetrofitClient` ve base URL backend, vi du:

```java
public static final String BACKEND_URL = "http://10.0.2.2:8000/api/";
```

Khi goi backend, khong gui header `apikey` nua. Cac API can dang nhap chi gui:

```text
Authorization: Bearer <access_token>
```

Mapping tu `SupabaseApi` cu:

```text
GET products              -> GET /api/products, tra ve List<Products>
GET products featured     -> GET /api/products/featured, tra ve List<Products>
GET users                 -> GET /api/users/me
PATCH users               -> PATCH /api/users/me
PATCH users compat        -> PATCH /api/users?id=eq.{id}
POST address              -> POST /api/address
PATCH address             -> PATCH /api/address/{address_id}
PATCH address compat      -> PATCH /api/address?id=eq.{id}
GET address               -> GET /api/address
DELETE address            -> DELETE /api/address/{address_id}
GET cart_items            -> GET /api/cart_items
POST cart_items           -> POST /api/cart_items
PATCH cart_items          -> PATCH /api/cart_items/{cart_item_id}
PATCH cart_items compat   -> PATCH /api/cart_items?id=eq.{id}
DELETE cart_items by id   -> DELETE /api/cart_items/{cart_item_id}
DELETE cart_items by user -> DELETE /api/cart_items
DELETE cart_items batch   -> DELETE /api/cart_items?ids=in.(id1,id2)
POST orders               -> POST /api/orders
POST order_items          -> POST /api/order_items
GET orders                -> GET /api/orders
GET reviews by item       -> GET /api/reviews?order_item_id={id}
GET reviews by items      -> GET /api/reviews?order_item_id=in.(id1,id2)
GET reviews by product    -> GET /api/reviews?product_id={id}
POST reviews              -> POST /api/reviews
POST signup               -> POST /api/auth/register
POST token password       -> POST /api/auth/login
POST token id_token       -> POST /api/auth/google
```

## Mapping Repository

### ProductRepository

- `getAllProducts()` -> `GET /api/products`
- `getFeaturedProducts()` -> `GET /api/products/featured`
- `searchProducts(query)` -> `GET /api/products?search={query}`

Backend cung ho tro tam thoi kieu filter cu:

```text
GET /api/products?name=ilike.*abc*
```

### CartRepository

- `getCartItems()` -> `GET /api/cart_items`
- `addToCart()` -> `POST /api/cart_items`
- `updateQuantity()` -> `PATCH /api/cart_items/{cart_item_id}`
- `removeFromCart()` -> `DELETE /api/cart_items/{cart_item_id}`
- `removeItemsFromCart()` -> `DELETE /api/cart_items?ids=in.(id1,id2)`
- `clearCart()` -> `DELETE /api/cart_items`

Backend tu lay `user_id` tu Bearer token, khong can truyen `userId` tu Android.

### HistoryRepository

- `getUserOrders()` -> `GET /api/orders`

Response da include `order_items`.

### OrderRepository

- `createOrder()` -> `POST /api/orders`
- `createOrderItems()` -> `POST /api/order_items`

`POST /api/orders` tra ve `List<Orders>` de khop `Call<List<Orders>>` hien tai.

### ProfileRepository

- `getUser()` -> `GET /api/users/me`
- `setUser()` -> `PATCH /api/users/me`
- `getAddress()` -> `GET /api/address`
- `setAddress()` -> `PATCH /api/address/{address_id}`
- `addAddress()` -> `POST /api/address`
- `deleteAddress()` -> `DELETE /api/address/{address_id}`
- `uploadToSupabase()` -> `POST /api/users/me/avatar?filename=avatar.jpg`

Upload avatar khong goi Supabase Storage truc tiep tu Android nua. Request body la bytes cua anh, header `Content-Type` la MIME type anh, vi du `image/jpeg`.

### ReviewRepository

- `checkReviewExists(orderItemId)` -> `GET /api/reviews?order_item_id={orderItemId}`
- `getReviewsForOrderItems(ids)` -> `GET /api/reviews?order_item_id=in.(id1,id2)`
- `getProductReviews(productId)` -> `GET /api/reviews?product_id={productId}`
- `submitReview()` -> `POST /api/reviews`

## Bang Supabase du kien

Code hien tai gia dinh cac bang sau:

- `users`: `id`, `name`, `email`, `phone`, `avatar_url`, `role`, `created_at`
- `products`: `id`, `name`, `brand`, `price`, `sale_price`, `stock`, `images`, `description`, `usage`, `indications`, `contraindications`, `manufacturer`, `requires_prescription`, `is_featured`, `is_best_seller`, `is_active`, `created_at`
- `address`: `id`, `user_id`, `recipient_name`, `location`, `location_name`, `phone_number`
- `cart_items`: `id`, `user_id`, `product_id`, `quantity`
- `orders`: `id`, `user_id`, `status`, `payment_method`, `total_amount`, `prescription_url`, `note`, `shipping_name`, `shipping_phone`, `shipping_address`, `created_at`, `updated_at`
- `order_items`: `id`, `order_id`, `product_id`, `product_name`, `product_image`, `price`, `quantity`
- `payments`: `id`, `order_id`, `method`, `amount`, `transaction_id`, `status`, `payment_data`
- `reviews`: `id`, `user_id`, `product_id`, `order_item_id`, `rating`, `comment`, `images`

Neu ten bang/cot trong Supabase hien tai khac, chi can sua trong cac file `app/services/*.py`.

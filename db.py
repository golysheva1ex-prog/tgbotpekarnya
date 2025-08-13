import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

import aiosqlite
from app.config import DB_PATH

# ---------------------- DDL ----------------------
CREATE_SQL = [
    # Пользователи с OTP
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER UNIQUE NOT NULL,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        is_verified INTEGER NOT NULL DEFAULT 0,
        otp_code_hash TEXT,
        otp_expires_at TEXT
    );
    """,
    # Адреса доставки
    """
    CREATE TABLE IF NOT EXISTS addresses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        address_line TEXT NOT NULL,
        apt TEXT,
        entrance TEXT,
        floor TEXT,
        comment TEXT,
        is_default INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """,
    # Категории
    """
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL
    );
    """,
    # Товары (со sort_order и фото)
    """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        sku TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        price_minor INTEGER NOT NULL,
        available INTEGER NOT NULL DEFAULT 1,
        photo_file_id TEXT,
        sort_order INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(category_id) REFERENCES categories(id)
    );
    """,
    # Заказы
    """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        status TEXT NOT NULL, -- cart/confirming/preparing/delivering/delivered/canceled
        delivery_type TEXT,   -- pickup/courier
        delivery_fee_minor INTEGER NOT NULL DEFAULT 0,
        subtotal_minor INTEGER NOT NULL DEFAULT 0,
        total_minor INTEGER NOT NULL DEFAULT 0,
        address_snapshot TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """,
    # Позиции заказа
    """
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        sku TEXT NOT NULL,
        title TEXT NOT NULL,
        unit_price_minor INTEGER NOT NULL,
        qty INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY(order_id) REFERENCES orders(id)
    );
    """,
    # Настройки
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """
]

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_users_tg ON users(tg_id)",
    "CREATE INDEX IF NOT EXISTS idx_categories_slug ON categories(slug)",
    "CREATE INDEX IF NOT EXISTS idx_products_cat ON products(category_id)",
    "CREATE INDEX IF NOT EXISTS idx_products_avail ON products(available)",
    "CREATE INDEX IF NOT EXISTS idx_products_sort ON products(sort_order, id DESC)",
    "CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)",
    "CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders(user_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id)"
]


# ---------------------- MIGRATIONS ----------------------
async def _migrate_users_add_otp(db: aiosqlite.Connection):
    cur = await db.execute("PRAGMA table_info(users)")
    cols = {r[1] for r in await cur.fetchall()}
    if "is_verified" not in cols:
        await db.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER NOT NULL DEFAULT 0")
    if "otp_code_hash" not in cols:
        await db.execute("ALTER TABLE users ADD COLUMN otp_code_hash TEXT")
    if "otp_expires_at" not in cols:
        await db.execute("ALTER TABLE users ADD COLUMN otp_expires_at TEXT")

async def _migrate_products_add_photo_sort(db: aiosqlite.Connection):
    cur = await db.execute("PRAGMA table_info(products)")
    cols = {r[1] for r in await cur.fetchall()}
    if "photo_file_id" not in cols:
        await db.execute("ALTER TABLE products ADD COLUMN photo_file_id TEXT")
    if "sort_order" not in cols:
        await db.execute("ALTER TABLE products ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")


# ---------------------- INIT ----------------------
async def init_db(default_courier_fee_rub: int = 150):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        # Таблицы
        for sql in CREATE_SQL:
            await db.execute(sql)
        # Миграции на случай старой БД
        await _migrate_users_add_otp(db)
        await _migrate_products_add_photo_sort(db)
        # Индексы
        for sql in INDEX_SQL:
            await db.execute(sql)
        # Значения по умолчанию
        await db.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES('courier_fee_minor', ?)",
            (default_courier_fee_rub * 100,)
        )
        # Служебная категория "Общее", если вдруг нет
        await db.execute("INSERT OR IGNORE INTO categories(slug, title) VALUES('general','Общее')")
        await db.commit()


# ---------------------- SETTINGS ----------------------
async def db_get_setting(key: str, default: Optional[str] = None) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return (row["value"] if row else (default or ""))

async def db_set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)", (key, value))
        await db.commit()


# ---------------------- USERS / OTP ----------------------
async def db_get_user_by_tg(tg_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

async def db_create_or_update_user_base(tg_id: int, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users(tg_id, name, phone, is_verified)
            VALUES(?, ?, '', 0)
            ON CONFLICT(tg_id) DO UPDATE SET name=excluded.name
        """, (tg_id, name))
        await db.commit()

async def db_set_user_phone_and_otp(tg_id: int, phone: str, otp_code_hash: str, expires_iso: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users
               SET phone = ?, otp_code_hash = ?, otp_expires_at = ?, is_verified = 0
             WHERE tg_id = ?
        """, (phone, otp_code_hash, expires_iso, tg_id))
        await db.commit()

async def db_mark_user_verified(tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users
               SET is_verified = 1, otp_code_hash = NULL, otp_expires_at = NULL
             WHERE tg_id = ?
        """, (tg_id,))
        await db.commit()


# ---------------------- ADDRESSES ----------------------
async def db_get_default_address(user_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT * FROM addresses
             WHERE user_id = ? AND is_default = 1
             ORDER BY id DESC LIMIT 1
        """, (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

async def db_set_default_address(user_id: int, addr: Dict[str, Any]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO addresses(user_id, address_line, apt, entrance, floor, comment, is_default)
            VALUES(?, ?, ?, ?, ?, ?, 1)
        """, (
            user_id,
            addr.get("address_line", ""),
            addr.get("apt"),
            addr.get("entrance"),
            addr.get("floor"),
            addr.get("comment"),
        ))
        await db.commit()


# ---------------------- CATEGORIES ----------------------
async def db_list_categories() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT id, slug, title FROM categories ORDER BY id ASC")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def db_get_category(cat_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT id, slug, title FROM categories WHERE id = ?", (cat_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

async def db_create_category(title: str, slug: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO categories(slug, title) VALUES(?, ?)", (slug, title))
        await db.commit()
        cur = await db.execute("SELECT last_insert_rowid()")
        rid = await cur.fetchone()
        return int(rid[0])

async def db_update_category_title(cat_id: int, title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE categories SET title = ? WHERE id = ?", (title, cat_id))
        await db.commit()

async def db_count_products_in_category(cat_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM products WHERE category_id = ?", (cat_id,))
        cnt = await cur.fetchone()
        return int(cnt[0] if cnt else 0)

async def db_delete_category(cat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        await db.commit()


# ---------------------- PRODUCTS ----------------------
async def db_list_products_public(
    page: int,
    page_size: int,
    search: Optional[str] = None,
    category_id: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Список товаров для пользователей (available=1) с пагинацией, опционально: поиск и фильтр по категории.
    Сортировка: sort_order ASC, id DESC.
    """
    offset = max(0, (page - 1) * max(1, page_size))
    where = ["available = 1"]
    params: List[Any] = []
    if category_id:
        where.append("category_id = ?")
        params.append(category_id)
    like = None
    if search:
        like = f"%{search.strip()}%"
        where.append("(title LIKE ? OR sku LIKE ?)")
        params.extend([like, like])

    where_sql = " AND ".join(where)
    sql_items = f"""
        SELECT id, sku, title, price_minor, available, photo_file_id, sort_order
          FROM products
         WHERE {where_sql}
         ORDER BY sort_order ASC, id DESC
         LIMIT ? OFFSET ?
    """
    sql_count = f"SELECT COUNT(*) AS cnt FROM products WHERE {where_sql}"

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # total
        cur = await db.execute(sql_count, params)
        total = (await cur.fetchone())["cnt"]

        # items
        cur2 = await db.execute(sql_items, params + [page_size, offset])
        rows = await cur2.fetchall()
        return [dict(r) for r in rows], int(total)

async def db_search_products_public(query: str, page: int, page_size: int) -> Tuple[List[Dict[str, Any]], int]:
    return await db_list_products_public(page=page, page_size=page_size, search=query)

async def db_list_products_by_category_admin(cat_id: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT p.id, p.sku, p.title, p.price_minor, p.available, p.photo_file_id, p.sort_order,
                   c.title AS category_title
              FROM products p
              JOIN categories c ON c.id = p.category_id
             WHERE p.category_id = ?
             ORDER BY p.sort_order ASC, p.id DESC
        """, (cat_id,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def db_list_products_admin(limit: int = 50) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT p.id, p.sku, p.title, p.price_minor, p.available, p.photo_file_id, p.sort_order
              FROM products p
             ORDER BY p.id DESC
             LIMIT ?
        """, (limit,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def db_get_product(prod_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM products WHERE id = ?", (prod_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

async def db_find_product_by_sku(sku: str) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM products WHERE sku = ?", (sku,))
        row = await cur.fetchone()
        return dict(row) if row else None

async def db_create_product(
    cat_id: int,
    title: str,
    price_minor: int,
    sku: str,
    available: int = 1,
    photo_file_id: Optional[str] = None,
    sort_order: int = 0
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO products(category_id, sku, title, price_minor, available, photo_file_id, sort_order)
            VALUES(?,?,?,?,?,?,?)
        """, (cat_id, sku, title, price_minor, available, photo_file_id, sort_order))
        await db.commit()
        cur = await db.execute("SELECT last_insert_rowid()")
        rid = await cur.fetchone()
        return int(rid[0])

async def db_update_product_title(prod_id: int, title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE products SET title = ? WHERE id = ?", (title, prod_id))
        await db.commit()

async def db_update_product_price(prod_id: int, price_minor: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE products SET price_minor = ? WHERE id = ?", (price_minor, prod_id))
        await db.commit()

async def db_set_product_available(prod_id: int, available: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE products SET available = ? WHERE id = ?", (available, prod_id))
        await db.commit()

async def db_update_product_photo(prod_id: int, photo_file_id: Optional[str]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE products SET photo_file_id = ? WHERE id = ?", (photo_file_id, prod_id))
        await db.commit()

async def db_update_product_sku(prod_id: int, new_sku: str) -> bool:
    """
    Обновить SKU. Возвращает True при успехе, False если SKU уже занят.
    """
    # проверим уникальность
    exists = await db_find_product_by_sku(new_sku)
    if exists and int(exists["id"]) != int(prod_id):
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE products SET sku = ? WHERE id = ?", (new_sku, prod_id))
        await db.commit()
    return True

async def db_update_product_sort_order(prod_id: int, sort_order: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE products SET sort_order = ? WHERE id = ?", (sort_order, prod_id))
        await db.commit()

async def db_delete_product(prod_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM products WHERE id = ?", (prod_id,))
        await db.commit()


# ---------------------- CART / ORDERS ----------------------
async def db_get_or_create_cart(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT id FROM orders
             WHERE user_id = ? AND status = 'cart'
             ORDER BY id DESC LIMIT 1
        """, (user_id,))
        row = await cur.fetchone()
        if row:
            return int(row["id"])
        created_at = datetime.utcnow().isoformat()
        await db.execute("""
            INSERT INTO orders(user_id, status, created_at, subtotal_minor, delivery_fee_minor, total_minor)
            VALUES(?, 'cart', ?, 0, 0, 0)
        """, (user_id, created_at))
        await db.commit()
        cur2 = await db.execute("SELECT last_insert_rowid() AS id")
        rid = await cur2.fetchone()
        return int(rid["id"])

async def db_add_item_to_cart(order_id: int, sku: str, title: str, unit_price_minor: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT id, qty FROM order_items
             WHERE order_id = ? AND sku = ?
        """, (order_id, sku))
        row = await cur.fetchone()
        if row:
            await db.execute("UPDATE order_items SET qty = ? WHERE id = ?", (int(row["qty"]) + 1, row["id"]))
        else:
            await db.execute("""
                INSERT INTO order_items(order_id, sku, title, unit_price_minor, qty)
                VALUES(?, ?, ?, ?, 1)
            """, (order_id, sku, title, unit_price_minor))
        await db.commit()

async def db_get_cart_items(order_id: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def db_update_order_totals(order_id: int, delivery_fee_minor: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT unit_price_minor, qty FROM order_items WHERE order_id = ?", (order_id,))
        items = await cur.fetchall()
        subtotal = sum(int(x["unit_price_minor"]) * int(x["qty"]) for x in items)
        total = subtotal + int(delivery_fee_minor)
        await db.execute("""
            UPDATE orders
               SET subtotal_minor = ?, delivery_fee_minor = ?, total_minor = ?
             WHERE id = ?
        """, (subtotal, delivery_fee_minor, total, order_id))
        await db.commit()

async def db_set_order_checkout(order_id: int, delivery_type: str, address_snapshot: Optional[Dict[str, Any]]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE orders
               SET status = 'confirming',
                   delivery_type = ?,
                   address_snapshot = ?
             WHERE id = ?
        """, (delivery_type, json.dumps(address_snapshot or {}, ensure_ascii=False), order_id))
        await db.commit()

async def db_get_order_basic(order_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

async def db_get_user_active_orders(limit: int = 20) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Вытаскиваем активные заказы + контакт пользователя
        cur = await db.execute("""
            SELECT o.*, u.name, u.phone, u.tg_id
              FROM orders o
              JOIN users u ON u.id = o.user_id
             WHERE o.status IN ('confirming','preparing','delivering')
             ORDER BY o.id DESC
             LIMIT ?
        """, (limit,))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def db_set_order_status(order_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        await db.commit()

async def db_clear_cart(order_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
        await db.execute("""
            UPDATE orders SET subtotal_minor = 0, delivery_fee_minor = 0, total_minor = 0
             WHERE id = ?
        """, (order_id,))
        await db.commit()

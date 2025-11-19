# ═══════════════════════════════════════════════════════════════════════════
# Aplicație Streamlit - Verificare Stoc SmartBill vs WooCommerce
# Versiune PostgreSQL DIRECT (psycopg v3) - Optimizat pentru Streamlit Cloud
# Data: 2025-11-19
# ═══════════════════════════════════════════════════════════════════════════

import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from datetime import datetime, timezone
import time
import traceback
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

st.set_page_config(
    page_title="Verificare Stoc SmartBill vs WooCommerce",
    page_icon="📦",
    layout="wide"
)

WAREHOUSE_NAME = "Eroilor 19 cv"

# ═══════════════════════════════════════════════════════════════════════════
# CONNECTION POOL POSTGRESQL
# ═══════════════════════════════════════════════════════════════════════════

@st.cache_resource
def get_connection_pool():
    """Creează connection pool PostgreSQL"""
    try:
        conninfo = f"host={st.secrets['postgresql']['host']} port={st.secrets['postgresql']['port']} dbname={st.secrets['postgresql']['database']} user={st.secrets['postgresql']['user']} password={st.secrets['postgresql']['password']}"
        connection_pool = ConnectionPool(conninfo, min_size=1, max_size=10)
        return connection_pool
    except Exception as e:
        st.error(f"Eroare connection pool: {e}")
        return None

def get_db_connection():
    """Obține conexiune din pool"""
    pool = get_connection_pool()
    if pool:
        try:
            return pool.getconn()
        except Exception as e:
            st.error(f"Eroare conexiune: {e}")
            return None
    return None

def release_db_connection(conn):
    """Returnează conexiunea în pool"""
    pool = get_connection_pool()
    if pool and conn:
        pool.putconn(conn)

# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR - CONFIGURĂRI + DEBUG
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("⚙️ Configurări")
    
    # SmartBill
    st.subheader("🔵 SmartBill")
    try:
        sb_email = st.secrets["smartbill"]["email"]
        sb_token = st.secrets["smartbill"]["token"]
        sb_cif = st.secrets["smartbill"]["cif"]
        st.success("✅ SmartBill")
    except:
        sb_email = st.text_input("Email")
        sb_token = st.text_input("Token", type="password")
        sb_cif = st.text_input("CIF")
    
    st.markdown("---")
    
    # WooCommerce
    st.subheader("🟢 WooCommerce")
    try:
        woo_url = st.secrets["woocommerce"]["url"]
        woo_key = st.secrets["woocommerce"]["consumer_key"]
        woo_secret = st.secrets["woocommerce"]["consumer_secret"]
        st.success("✅ WooCommerce")
    except:
        woo_url = st.text_input("URL")
        woo_key = st.text_input("Consumer Key", type="password")
        woo_secret = st.text_input("Consumer Secret", type="password")
    
    st.markdown("---")
    
    # PostgreSQL
    st.subheader("💾 PostgreSQL")
    try:
        test_conn = get_db_connection()
        if test_conn:
            test_conn.close()
            release_db_connection(test_conn)
            st.success("✅ PostgreSQL OK")
            db_connected = True
        else:
            st.error("❌ Eroare PostgreSQL")
            db_connected = False
    except:
        st.error("❌ Configurare lipsă!")
        db_connected = False
    
    st.markdown("---")
    st.subheader("🔧 Debug Panel")
    
    if st.button("🔍 Verifică Tabele", use_container_width=True):
        if db_connected:
            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor(row_factory=dict_row)
                    cursor.execute("SELECT COUNT(*) as count FROM public.woocommerce_stock")
                    count = cursor.fetchone()['count']
                    st.metric("Total Rânduri", count)
                    
                    cursor.execute("SELECT * FROM public.woocommerce_stock LIMIT 5")
                    sample = cursor.fetchall()
                    if sample:
                        st.dataframe(pd.DataFrame(sample))
                    
                    st.success("✅ Tabelă OK!")
                    cursor.close()
                except Exception as e:
                    st.error(f"❌ Eroare: {e}")
                finally:
                    release_db_connection(conn)

    if st.button("🧪 Test WooCommerce API", use_container_width=True):
        if all([woo_url, woo_key, woo_secret]):
            try:
                r = requests.get(f"{woo_url}/wp-json/wc/v3/products", auth=(woo_key, woo_secret), params={"per_page": 1}, timeout=10)
                if r.status_code == 200:
                    st.success("✅ API OK")
                else:
                    st.error(f"❌ Status: {r.status_code}")
            except Exception as e:
                st.error(f"❌ Eroare: {e}")

    if st.button("📊 Info Database", use_container_width=True):
        if db_connected:
            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor(row_factory=dict_row)
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total,
                            COUNT(*) FILTER (WHERE stock_status = 'instock') as in_stock,
                            COUNT(*) FILTER (WHERE stock_status = 'outofstock') as out_of_stock,
                            SUM(stock_quantity) as total_qty
                        FROM public.woocommerce_stock
                    """)
                    stats = cursor.fetchone()
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Total", stats['total'])
                        st.metric("În Stoc", stats['in_stock'])
                    with col2:
                        st.metric("Fără Stoc", stats['out_of_stock'])
                        st.metric("Cantitate", f"{stats['total_qty']:.0f}")
                    
                    cursor.close()
                except Exception as e:
                    st.error(f"❌ Eroare: {e}")
                finally:
                    release_db_connection(conn)

# ═══════════════════════════════════════════════════════════════════════════
# FUNCȚII PRINCIPALE
# ═══════════════════════════════════════════════════════════════════════════

def update_stocks_only(woo_url, woo_key, woo_secret):
    """Update rapid stocuri pentru produse existente"""
    st.markdown("---")
    st.subheader("⚡ Update Rapid Stocuri")
    
    try:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        conn = get_db_connection()
        if not conn:
            st.error("❌ Nu pot obține conexiune PostgreSQL!")
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT sku FROM public.woocommerce_stock")
            existing_skus = set(row[0] for row in cursor.fetchall())
            cursor.close()
            
            st.info(f"📦 {len(existing_skus)} SKU-uri în baza de date")
            progress_bar.progress(0.2)
            
            status_text.text("📥 Preluare stocuri din WooCommerce...")
            stock_dict = {}
            page = 1
            
            while True:
                try:
                    response = requests.get(
                        f"{woo_url}/wp-json/wc/v3/products",
                        auth=(woo_key, woo_secret),
                        params={"per_page": 100, "page": page, "status": "publish", "_fields": "sku,stock_quantity,stock_status"},
                        timeout=30
                    )
                    
                    if response.status_code != 200:
                        break
                    
                    products = response.json()
                    if not products:
                        break
                    
                    for p in products:
                        sku = p.get('sku', '').strip()
                        if sku and sku in existing_skus:
                            stock_dict[sku] = {
                                'stock_quantity': float(p.get('stock_quantity') or 0),
                                'stock_status': p.get('stock_status', 'outofstock'),
                                'last_synced_at': datetime.now(timezone.utc)
                            }
                    
                    status_text.text(f"📥 {len(stock_dict)} stocuri actualizate (pagina {page})...")
                    page += 1
                    time.sleep(0.1)
                    
                except Exception as e:
                    st.warning(f"Eroare pagina {page}: {e}")
                    break
            
            progress_bar.progress(0.8)
            
            if stock_dict:
                status_text.text(f"💾 Salvare {len(stock_dict)} actualizări...")
                
                cursor = conn.cursor()
                update_query = "UPDATE public.woocommerce_stock SET stock_quantity = %s, stock_status = %s, last_synced_at = %s WHERE sku = %s"
                update_data = [(v['stock_quantity'], v['stock_status'], v['last_synced_at'], k) for k, v in stock_dict.items()]
                
                cursor.executemany(update_query, update_data)
                conn.commit()
                
                updated = cursor.rowcount
                cursor.close()
                
                progress_bar.progress(1.0)
                time.sleep(0.3)
                progress_bar.empty()
                status_text.empty()
                st.success(f"✅ {updated} stocuri actualizate!")
                return True
            else:
                st.warning("⚠️ Nu s-au găsit stocuri de actualizat")
                return False
                
        finally:
            release_db_connection(conn)
            
    except Exception as e:
        st.error(f"❌ EROARE: {e}")
        st.code(traceback.format_exc())
        return False

def sync_woocommerce_full(woo_url, woo_key, woo_secret):
    """Sincronizare completă WooCommerce → PostgreSQL"""
    st.markdown("---")
    st.subheader("🔄 Sincronizare Completă")
    
    progress_container = st.container()
    result_container = st.container()
    log_container = st.container()
    
    start_time = datetime.now()
    log_lines = [f"🕐 Start: {start_time.strftime('%H:%M:%S')}"]
    
    try:
        with progress_container:
            progress_bar = st.progress(0)
            status_text = st.empty()
            info_box = st.empty()
        
        with log_container:
            log_display = st.empty()
            log_display.text('\n'.join(log_lines))
        
        # STEP 1: Preluare produse
        log_lines.append("📥 STEP 1: Preluare produse...")
        with log_container:
            log_display.text('\n'.join(log_lines))
        
        all_items = []
        page = 1
        products_data = []
        
        while True:
            try:
                response = requests.get(
                    f"{woo_url}/wp-json/wc/v3/products",
                    auth=(woo_key, woo_secret),
                    params={"per_page": 100, "page": page, "status": "publish"},
                    timeout=60
                )
                
                if response.status_code != 200:
                    break
                
                products = response.json()
                if not products:
                    break
                
                products_data.extend(products)
                
                with progress_container:
                    status_text.text(f"📥 {len(products_data)} produse (pagina {page})...")
                
                page += 1
                time.sleep(0.1)
                
            except:
                break
        
        progress_bar.progress(0.2)
        log_lines.append(f"✅ STEP 1: {len(products_data)} produse preluate")
        
        simple = [p for p in products_data if p.get('type') in ['simple', 'external', 'grouped']]
        variable = [p for p in products_data if p.get('type') == 'variable']
        
        with progress_container:
            info_box.info(f"📦 Simple: {len(simple)} | Variabile: {len(variable)}")
        
        all_items.extend(simple)
        log_lines.append(f"📊 Tipuri: Simple {len(simple)} | Variabile {len(variable)}")
        with log_container:
            log_display.text('\n'.join(log_lines))
        
        # STEP 2: Variații
        if variable:
            log_lines.append("🔄 STEP 2: Preluare variații...")
            with log_container:
                log_display.text('\n'.join(log_lines))
            
            total_var = 0
            
            for idx, vp in enumerate(variable, 1):
                product_id = vp['id']
                vpage = 1
                
                while True:
                    try:
                        vr = requests.get(
                            f"{woo_url}/wp-json/wc/v3/products/{product_id}/variations",
                            auth=(woo_key, woo_secret),
                            params={"per_page": 100, "page": vpage},
                            timeout=60
                        )
                        
                        if vr.status_code != 200:
                            break
                        
                        vlist = vr.json()
                        if not vlist:
                            break
                        
                        all_items.extend(vlist)
                        total_var += len(vlist)
                        vpage += 1
                        time.sleep(0.05)
                        
                    except:
                        break
                
                with progress_container:
                    status_text.text(f"🔄 {idx}/{len(variable)} produse ({total_var} variații)")
                    progress_bar.progress(0.2 + (0.5 * (idx / len(variable))))
            
            log_lines.append(f"✅ STEP 2: {total_var} variații preluate")
            with log_container:
                log_display.text('\n'.join(log_lines))
        
        progress_bar.progress(0.7)
        
        # STEP 3: Procesare date
        log_lines.append("💾 STEP 3: Procesare și deduplicare...")
        with log_container:
            log_display.text('\n'.join(log_lines))
        
        sku_map = {}
        duplicate_details = []
        
        for item in all_items:
            sku = item.get('sku', '').strip()
            if not sku:
                continue
            
            if sku in sku_map:
                duplicate_details.append({'sku': sku, 'first_id': sku_map[sku]['id'], 'duplicate_id': item.get('id')})
            
            sku_map[sku] = {
                'id': item.get('id'),
                'type': item.get('type', 'unknown'),
                'stock': item.get('stock_quantity'),
                'status': item.get('stock_status', 'outofstock')
            }
        
        log_lines.append(f"✅ STEP 3: {len(sku_map)} SKU-uri unice, {len(duplicate_details)} duplicate")
        with log_container:
            log_display.text('\n'.join(log_lines))
        
        progress_bar.progress(0.8)
        
        # STEP 4: Salvare în PostgreSQL
        log_lines.append("💾 STEP 4: Salvare în PostgreSQL...")
        with log_container:
            log_display.text('\n'.join(log_lines))
        
        conn = get_db_connection()
        if not conn:
            st.error("❌ Nu pot obține conexiune PostgreSQL!")
            return False
        
        try:
            cursor = conn.cursor()
            
            stock_data = [
                (sku, float(prod['stock']) if prod['stock'] is not None else 0, prod['status'], prod['type'], prod['id'], datetime.now(timezone.utc))
                for sku, prod in sku_map.items()
            ]
            
            # Upsert manual (psycopg v3)
            upsert_query = """
                INSERT INTO public.woocommerce_stock (sku, stock_quantity, stock_status, product_type, woo_product_id, last_synced_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (sku) DO UPDATE SET
                    stock_quantity = EXCLUDED.stock_quantity,
                    stock_status = EXCLUDED.stock_status,
                    product_type = EXCLUDED.product_type,
                    woo_product_id = EXCLUDED.woo_product_id,
                    last_synced_at = EXCLUDED.last_synced_at
            """
            
            cursor.executemany(upsert_query, stock_data)
            conn.commit()
            
            saved = len(stock_data)
            cursor.close()
            
            end_time = datetime.now()
            duration = (end_time - start_time).seconds
            
            log_lines.append(f"✅ STEP 4: {saved} produse salvate")
            log_lines.append(f"🏁 Finalizat în {duration}s ({duration//60}m {duration%60}s)")
            with log_container:
                log_display.text('\n'.join(log_lines))
            
            progress_bar.progress(1.0)
            time.sleep(0.3)
            progress_container.empty()
            
            with result_container:
                st.subheader("✅ Sincronizare Completă!")
                st.success(f"🎉 {saved} produse salvate în {duration//60}m {duration%60}s")
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("📦 Produse totale", len(all_items))
                col2.metric("💾 Salvate", saved)
                col3.metric("🔄 SKU-uri unice", len(sku_map))
                col4.metric("⏱️ Timp", f"{duration//60}m {duration%60}s")
                
                if duplicate_details:
                    st.markdown("---")
                    st.warning(f"⚠️ {len(duplicate_details)} SKU-uri duplicate detectate")
            
            return True
            
        finally:
            release_db_connection(conn)
        
    except Exception as e:
        st.error(f"❌ EROARE: {e}")
        st.code(traceback.format_exc())
        return False

def get_woocommerce_stock_from_db():
    """Citește toate stocurile din PostgreSQL"""
    try:
        conn = get_db_connection()
        if not conn:
            return {}
        
        try:
            cursor = conn.cursor(row_factory=dict_row)
            cursor.execute("SELECT sku, stock_quantity, stock_status FROM public.woocommerce_stock")
            rows = cursor.fetchall()
            cursor.close()
            
            return {row['sku']: {'stock': float(row['stock_quantity']), 'status': row['stock_status']} for row in rows}
        finally:
            release_db_connection(conn)
            
    except Exception as e:
        st.error(f"Eroare citire PostgreSQL: {e}")
        return {}

def get_smartbill_stocks(email, token, cif, warehouse_name):
    """Preluare stocuri din SmartBill"""
    try:
        r = requests.get(
            "https://ws.smartbill.ro/SBORO/api/stocks",
            auth=HTTPBasicAuth(email, token),
            headers={"Accept": "application/json"},
            params={"cif": cif, "date": datetime.now().strftime("%Y-%m-%d"), "warehouseName": warehouse_name},
            timeout=30
        )
        return r.json() if r.status_code == 200 else None
    except:
        return None

def process_smartbill_data(data):
    """Procesare date SmartBill"""
    sb_dict = {}
    if not data:
        return sb_dict
    
    products = []
    if isinstance(data, dict) and "list" in data:
        for w in data["list"]:
            if isinstance(w, dict) and "products" in w:
                products.extend(w["products"])
    
    for p in products:
        if not isinstance(p, dict):
            continue
        code = p.get('productCode', '').strip()
        if code:
            sb_dict[code] = {'name': p.get('productName', ''), 'stock': float(p.get('quantity', 0))}
    
    return sb_dict

def generate_discrepancy_report(sb_dict, woo_dict):
    """Generare raport discrepanțe"""
    disc = []
    
    for code, sb in sb_dict.items():
        if code not in woo_dict and sb['stock'] > 0:
            disc.append({'SKU': code, 'Denumire': sb['name'][:60], 'Stoc SB': float(sb['stock']), 'Stoc Woo': 0.0, 'Diferență': float(sb['stock']), 'Tip': 'Lipsă în Woo', 'Status': 'CRITIC', 'Prioritate': 1})
    
    for code, sb in sb_dict.items():
        if code in woo_dict and sb['stock'] > 0 and woo_dict[code]['stock'] == 0:
            disc.append({'SKU': code, 'Denumire': sb['name'][:60], 'Stoc SB': float(sb['stock']), 'Stoc Woo': 0.0, 'Diferență': float(sb['stock']), 'Tip': 'Stoc 0 în Woo', 'Status': 'ATENȚIE', 'Prioritate': 2})
    
    for code in set(sb_dict.keys()) & set(woo_dict.keys()):
        sb_stock = sb_dict[code]['stock']
        woo_stock = woo_dict[code]['stock']
        diff = sb_stock - woo_stock
        
        if abs(diff) > 0.01 and sb_stock > 0:
            disc.append({'SKU': code, 'Denumire': sb_dict[code]['name'][:60], 'Stoc SB': float(sb_stock), 'Stoc Woo': float(woo_stock), 'Diferență': round(float(diff), 2), 'Tip': 'Diferență', 'Status': 'SYNC', 'Prioritate': 3})
    
    for code, woo in woo_dict.items():
        if code not in sb_dict and woo['stock'] > 0:
            disc.append({'SKU': code, 'Denumire': '', 'Stoc SB': 0.0, 'Stoc Woo': float(woo['stock']), 'Diferență': -float(woo['stock']), 'Tip': 'În Woo nu în SB', 'Status': 'VERIFICARE', 'Prioritate': 4})
    
    df = pd.DataFrame(disc)
    if len(df) > 0:
        df = df.sort_values(['Prioritate', 'Stoc SB'], ascending=[True, False])
        df = df.drop('Prioritate', axis=1)
    
    return df

# ═══════════════════════════════════════════════════════════════════════════
# UI PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

st.title("📦 Verificare Stoc: SmartBill vs WooCommerce")
st.caption("Versiune PostgreSQL DIRECT (psycopg v3) - Optimizat Streamlit Cloud")
st.markdown("---")

if db_connected:
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(row_factory=dict_row)
            cursor.execute("SELECT COUNT(*) as total FROM public.woocommerce_stock")
            total = cursor.fetchone()['total']
            
            cursor.execute("SELECT last_synced_at FROM public.woocommerce_stock WHERE last_synced_at IS NOT NULL ORDER BY last_synced_at DESC LIMIT 1")
            last_sync_row = cursor.fetchone()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("📦 Produse în baza de date", total)
            with col2:
                if last_sync_row:
                    st.info(f"📅 Ultima sincronizare: {last_sync_row['last_synced_at']} (UTC)")
                else:
                    st.info("📅 Nicio sincronizare încă")
            
            cursor.close()
        except Exception as e:
            st.error(f"⚠️ Eroare citire info: {e}")
        finally:
            release_db_connection(conn)

st.markdown("---")

c1, c2, c3 = st.columns(3)

with c1:
    quick = st.button("⚡ Update Rapid Stocuri", type="primary", use_container_width=True)

with c2:
    full = st.button("🔄 Sincronizare Completă", type="secondary", use_container_width=True)

with c3:
    report = st.button("📊 Raport Discrepanțe", type="secondary", use_container_width=True)

if quick:
    if not db_connected or not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Configurează toate serviciile!")
    else:
        update_stocks_only(woo_url, woo_key, woo_secret)

if full:
    if not db_connected or not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Configurează toate serviciile!")
    else:
        sync_woocommerce_full(woo_url, woo_key, woo_secret)

if report:
    if not db_connected or not all([sb_email, sb_token, sb_cif]):
        st.error("⚠️ Configurează SmartBill și PostgreSQL!")
    else:
        st.markdown("---")
        st.subheader("📊 Generare Raport Discrepanțe")
        
        with st.spinner("📥 Preluare date..."):
            woo_dict = get_woocommerce_stock_from_db()
            sb_data = get_smartbill_stocks(sb_email, sb_token, sb_cif, WAREHOUSE_NAME)
        
        if woo_dict and sb_data:
            sb_dict = process_smartbill_data(sb_data)
            
            col1, col2 = st.columns(2)
            col1.metric("Produse WooCommerce (DB)", len(woo_dict))
            col2.metric("Produse SmartBill", len(sb_dict))
            
            df = generate_discrepancy_report(sb_dict, woo_dict)
            
            if len(df) > 0:
                st.markdown("---")
                st.header("📊 Discrepanțe Detectate")
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🔴 CRITIC", len(df[df['Status'] == 'CRITIC']))
                m2.metric("🟡 ATENȚIE", len(df[df['Status'] == 'ATENȚIE']))
                m3.metric("🔵 SYNC", len(df[df['Status'] == 'SYNC']))
                m4.metric("📝 Total", len(df))
                
                st.markdown("---")
                
                f1, f2 = st.columns([1, 2])
                with f1:
                    status_filter = st.multiselect("Filtrează după Status", df['Status'].unique(), df['Status'].unique())
                with f2:
                    search = st.text_input("🔎 Caută SKU sau Denumire")
                
                df_filtered = df[df['Status'].isin(status_filter)]
                
                if search:
                    df_filtered = df_filtered[
                        df_filtered['SKU'].astype(str).str.contains(search, case=False, na=False) |
                        df_filtered['Denumire'].astype(str).str.contains(search, case=False, na=False)
                    ]
                
                st.dataframe(df_filtered, use_container_width=True, height=450, hide_index=True)
                
                st.caption(f"Afișate {len(df_filtered)} din {len(df)} discrepanțe")
                
                csv = df_filtered.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 Descarcă CSV", csv, f"raport_discrepante_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv")
            else:
                st.success("🎉 Nu există discrepanțe! Totul este sincronizat corect!")
                st.balloons()
        else:
            st.error("❌ Nu s-au putut prelua datele!")

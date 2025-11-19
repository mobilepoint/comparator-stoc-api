# ═══════════════════════════════════════════════════════════════════════════
# Aplicație Streamlit - Verificare Stoc SmartBill vs WooCommerce
# Versiune POST-MIGRARE SUPABASE - cu DEBUG Panel
# Data: 2025-11-19
# ═══════════════════════════════════════════════════════════════════════════

import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from datetime import datetime, timezone
from supabase import create_client, Client
import time
import traceback

st.set_page_config(
    page_title="Verificare Stoc SmartBill vs WooCommerce",
    page_icon="📦",
    layout="wide"
)

WAREHOUSE_NAME = "Eroilor 19 cv"

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
        st.success("✅ SmartBill configurat")
    except:
        sb_email = st.text_input("Email", value="mobilepointgsm@gmail.com")
        sb_token = st.text_input("Token", type="password")
        sb_cif = st.text_input("CIF", value="RO36898183")

    st.markdown("---")

    # WooCommerce
    st.subheader("🟢 WooCommerce")
    try:
        woo_url = st.secrets["woocommerce"]["url"]
        woo_key = st.secrets["woocommerce"]["consumer_key"]
        woo_secret = st.secrets["woocommerce"]["consumer_secret"]
        st.success("✅ WooCommerce configurat")
    except:
        woo_url = st.text_input("URL", value="https://servicepack.ro")
        woo_key = st.text_input("Consumer Key", type="password")
        woo_secret = st.text_input("Consumer Secret", type="password")

    st.markdown("---")

    # Supabase
    st.subheader("💾 Supabase")
    try:
        supabase_url = st.secrets["supabase"]["url"]
        supabase_key = st.secrets["supabase"]["key"]
        supabase: Client = create_client(supabase_url, supabase_key)
        st.success("✅ Conectat la Supabase")
    except Exception as e:
        st.error(f"❌ Eroare Supabase: {e}")
        supabase_url = st.text_input("Supabase URL")
        supabase_key = st.text_input("Supabase Key", type="password")
        if supabase_url and supabase_key:
            try:
                supabase = create_client(supabase_url, supabase_key)
                st.success("✅ Conectat manual")
            except Exception as e:
                st.error(f"❌ Eroare conexiune: {e}")
                supabase = None
        else:
            supabase = None

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════
    # 🔧 DEBUG PANEL
    # ═══════════════════════════════════════════════════════════════════════

    st.subheader("🔧 Debug Panel")

    if st.button("🔍 Verifică Tabele", use_container_width=True):
        if not supabase:
            st.error("❌ Supabase nu este conectat!")
        else:
            with st.spinner("Verificare în curs..."):
                debug_results = {}

                # 1. Verifică dacă tabela woocommerce_stock există
                try:
                    result = supabase.table('woocommerce_stock').select('*', count='exact').limit(1).execute()
                    debug_results['woocommerce_stock'] = {
                        'exists': True,
                        'count': result.count if hasattr(result, 'count') else len(result.data),
                        'status': '✅'
                    }
                except Exception as e:
                    debug_results['woocommerce_stock'] = {
                        'exists': False,
                        'error': str(e),
                        'status': '❌'
                    }

                # 2. Verifică schema
                try:
                    test = supabase.table('woocommerce_stock').select('sku').limit(1).execute()
                    debug_results['connection'] = {'status': '✅', 'message': 'Conexiune OK'}
                except Exception as e:
                    debug_results['connection'] = {'status': '❌', 'message': f'Eroare: {e}'}

                # Afișează rezultatele
                st.markdown("### 📊 Rezultate Verificare:")

                for key, val in debug_results.items():
                    with st.expander(f"{val['status']} {key}"):
                        st.json(val)

                # Verificare suplimentară - primele rânduri
                if debug_results['woocommerce_stock']['exists']:
                    try:
                        sample = supabase.table('woocommerce_stock').select('*').limit(5).execute()
                        st.markdown("#### 📝 Primele 5 rânduri:")
                        if sample.data:
                            st.dataframe(pd.DataFrame(sample.data))
                        else:
                            st.info("Tabela este goală")
                    except:
                        pass

    if st.button("🧪 Test WooCommerce API", use_container_width=True):
        if not all([woo_url, woo_key, woo_secret]):
            st.error("❌ Configurează WooCommerce!")
        else:
            with st.spinner("Testare API..."):
                try:
                    response = requests.get(
                        f"{woo_url}/wp-json/wc/v3/products",
                        auth=(woo_key, woo_secret),
                        params={"per_page": 1},
                        timeout=10
                    )
                    if response.status_code == 200:
                        st.success(f"✅ API OK (status: {response.status_code})")
                        st.json(response.json()[0] if response.json() else {})
                    else:
                        st.error(f"❌ Status: {response.status_code}")
                        st.text(response.text[:500])
                except Exception as e:
                    st.error(f"❌ Eroare: {e}")

    if st.button("📊 Info Database", use_container_width=True):
        if not supabase:
            st.error("❌ Supabase nu este conectat!")
        else:
            with st.spinner("Citire info..."):
                try:
                    # Număr total produse
                    count_result = supabase.table('woocommerce_stock').select('*', count='exact').limit(1).execute()
                    total = count_result.count if hasattr(count_result, 'count') else 0

                    # Ultima sincronizare
                    last_sync_result = supabase.table('woocommerce_stock').select('last_synced_at').order('last_synced_at', desc=True).limit(1).execute()
                    last_sync = last_sync_result.data[0]['last_synced_at'] if last_sync_result.data else 'N/A'

                    # Statistici stocuri
                    all_data = []
                    offset = 0
                    batch_size = 1000
                    while True:
                        result = supabase.table('woocommerce_stock').select('stock_quantity,stock_status').range(offset, offset + batch_size - 1).execute()
                        if not result.data:
                            break
                        all_data.extend(result.data)
                        offset += batch_size
                        if len(result.data) < batch_size:
                            break

                    df = pd.DataFrame(all_data)
                    in_stock = len(df[df['stock_status'] == 'instock'])
                    out_of_stock = len(df[df['stock_status'] == 'outofstock'])
                    total_qty = df['stock_quantity'].sum()

                    st.markdown("### 📊 Statistici Database:")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Total Produse", total)
                        st.metric("În Stoc", in_stock)
                        st.metric("Fără Stoc", out_of_stock)
                    with col2:
                        st.metric("Cantitate Totală", f"{total_qty:.0f}")
                        st.text(f"Ultima sync:\n{last_sync}")

                except Exception as e:
                    st.error(f"❌ Eroare: {e}")
                    st.code(traceback.format_exc())

# ═══════════════════════════════════════════════════════════════════════════
# FUNCȚII PRINCIPALE
# ═══════════════════════════════════════════════════════════════════════════

def update_stocks_only(woo_url, woo_key, woo_secret, supabase_client):
    """Update rapid stocuri pentru produse existente"""
    st.markdown("---")
    st.subheader("⚡ Update Rapid Stocuri")

    try:
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Citire SKU-uri existente
        status_text.text("📥 Citire SKU-uri din Supabase...")
        existing_skus = set()
        offset = 0
        batch_size = 1000

        while True:
            try:
                result = supabase_client.table('woocommerce_stock').select('sku').range(offset, offset + batch_size - 1).execute()
                if not result.data:
                    break
                for row in result.data:
                    existing_skus.add(row['sku'])
                offset += batch_size
                status_text.text(f"📥 {len(existing_skus)} SKU-uri citite...")
                if len(result.data) < batch_size:
                    break
            except Exception as e:
                st.error(f"Eroare citire DB: {e}")
                return False

        st.info(f"📦 {len(existing_skus)} SKU-uri în baza de date")
        progress_bar.progress(0.2)

        # Preluare stocuri WooCommerce
        status_text.text("📥 Preluare stocuri din WooCommerce...")
        stock_dict = {}
        page = 1

        while True:
            try:
                response = requests.get(
                    f"{woo_url}/wp-json/wc/v3/products",
                    auth=(woo_key, woo_secret),
                    params={
                        "per_page": 100,
                        "page": page,
                        "status": "publish",
                        "_fields": "sku,stock_quantity,stock_status"
                    },
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
                            'sku': sku,
                            'stock_quantity': float(p.get('stock_quantity') or 0),
                            'stock_status': p.get('stock_status', 'outofstock'),
                            'last_synced_at': datetime.now(timezone.utc).isoformat()
                        }

                status_text.text(f"📥 {len(stock_dict)} stocuri actualizate (pagina {page})...")
                page += 1
                time.sleep(0.1)

            except Exception as e:
                st.warning(f"Eroare pagina {page}: {e}")
                break

        stock_updates = list(stock_dict.values())
        progress_bar.progress(0.8)

        # Salvare în Supabase
        if stock_updates:
            status_text.text(f"💾 Salvare {len(stock_updates)} actualizări...")
            updated = 0

            for i in range(0, len(stock_updates), 500):
                batch = stock_updates[i:i+500]
                try:
                    supabase_client.table('woocommerce_stock').upsert(batch).execute()
                    updated += len(batch)
                except:
                    for item in batch:
                        try:
                            supabase_client.table('woocommerce_stock').upsert([item]).execute()
                            updated += 1
                        except:
                            pass

            progress_bar.progress(1.0)
            time.sleep(0.3)
            progress_bar.empty()
            status_text.empty()
            st.success(f"✅ {updated} stocuri actualizate din {len(stock_updates)}")
            return True
        else:
            st.warning("⚠️ Nu s-au găsit stocuri de actualizat")
            return False

    except Exception as e:
        st.error(f"❌ EROARE: {e}")
        st.code(traceback.format_exc())
        return False

def sync_woocommerce_full(woo_url, woo_key, woo_secret, supabase_client):
    """Sincronizare completă WooCommerce → Supabase"""
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
        with progress_container:
            status_text.text("📥 Preluare produse principale...")

        log_lines.append("📥 STEP 1: Preluare produse...")
        with log_container:
            log_display.text('\n'.join(log_lines))

        all_items = []
        page = 1
        products_data = []
        products_failed = 0

        while True:
            try:
                response = requests.get(
                    f"{woo_url}/wp-json/wc/v3/products",
                    auth=(woo_key, woo_secret),
                    params={"per_page": 100, "page": page, "status": "publish"},
                    timeout=60
                )

                if response.status_code != 200:
                    log_lines.append(f"⚠️ Pagina {page}: Status {response.status_code}")
                    with log_container:
                        log_display.text('\n'.join(log_lines))
                    products_failed += 1
                    if products_failed > 3:
                        break
                    continue

                products = response.json()
                if not products:
                    break

                products_data.extend(products)

                with progress_container:
                    status_text.text(f"📥 {len(products_data)} produse (pagina {page})...")

                page += 1
                time.sleep(0.1)

            except Exception as e:
                log_lines.append(f"❌ Eroare pagina {page}: {str(e)[:50]}")
                with log_container:
                    log_display.text('\n'.join(log_lines))
                products_failed += 1
                if products_failed > 3:
                    break

        with progress_container:
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
            with progress_container:
                status_text.text("🔄 Preluare variații...")

            log_lines.append("🔄 STEP 2: Preluare variații...")
            with log_container:
                log_display.text('\n'.join(log_lines))

            total_var = 0
            failed_products = []

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
                            failed_products.append(f"{product_id} ({vr.status_code})")
                            break

                        vlist = vr.json()
                        if not vlist:
                            break

                        all_items.extend(vlist)
                        total_var += len(vlist)
                        vpage += 1
                        time.sleep(0.05)

                    except Exception as e:
                        failed_products.append(f"{product_id} ({str(e)[:30]})")
                        log_lines.append(f"⚠️ Produs {product_id}: {str(e)[:50]}")
                        with log_container:
                            log_display.text('\n'.join(log_lines))
                        break

                with progress_container:
                    status_text.text(f"🔄 {idx}/{len(variable)} produse ({total_var} variații)")
                    progress_bar.progress(0.2 + (0.5 * (idx / len(variable))))

                if idx % 50 == 0:
                    elapsed = (datetime.now() - start_time).seconds
                    log_lines.append(f"📍 Checkpoint {idx}/{len(variable)}: {total_var} variații ({elapsed}s)")
                    with log_container:
                        log_display.text('\n'.join(log_lines))

            log_lines.append(f"✅ STEP 2: {total_var} variații preluate")
            if failed_products:
                log_lines.append(f"⚠️ {len(failed_products)} produse eșuate")
            with log_container:
                log_display.text('\n'.join(log_lines))

        with progress_container:
            progress_bar.progress(0.7)
            info_box.success(f"✅ Total: {len(all_items)} produse")

        # STEP 3: Procesare date
        log_lines.append("💾 STEP 3: Procesare și deduplicare...")
        with log_container:
            log_display.text('\n'.join(log_lines))

        with progress_container:
            status_text.text("💾 Procesare date...")

        sku_map = {}
        duplicate_details = []

        for item in all_items:
            sku = item.get('sku', '').strip()
            if not sku:
                continue

            if sku in sku_map:
                duplicate_details.append({
                    'sku': sku,
                    'first_id': sku_map[sku]['id'],
                    'duplicate_id': item.get('id')
                })

            sku_map[sku] = {
                'id': item.get('id'),
                'name': item.get('name', ''),
                'type': item.get('type', 'unknown'),
                'stock': item.get('stock_quantity'),
                'status': item.get('stock_status', 'outofstock')
            }

        log_lines.append(f"✅ STEP 3: {len(sku_map)} SKU-uri unice, {len(duplicate_details)} duplicate")
        with log_container:
            log_display.text('\n'.join(log_lines))

        with progress_container:
            progress_bar.progress(0.8)

        # STEP 4: Salvare în Supabase
        log_lines.append("💾 STEP 4: Salvare în Supabase...")
        with log_container:
            log_display.text('\n'.join(log_lines))

        stock_data = []
        for sku, prod in sku_map.items():
            stock_data.append({
                'sku': sku,
                'stock_quantity': float(prod['stock']) if prod['stock'] is not None else 0,
                'stock_status': prod['status'],
                'product_type': prod['type'],
                'woo_product_id': prod['id'],
                'last_synced_at': datetime.now(timezone.utc).isoformat()
            })

        with progress_container:
            status_text.text(f"💾 Salvare {len(stock_data)} produse...")

        saved = 0
        failed_saves = 0

        for i in range(0, len(stock_data), 500):
            batch = stock_data[i:i+500]
            try:
                supabase_client.table('woocommerce_stock').upsert(batch).execute()
                saved += len(batch)

                with progress_container:
                    status_text.text(f"💾 {saved}/{len(stock_data)} salvate...")
                    progress_bar.progress(0.8 + (0.2 * (saved / len(stock_data))))

            except Exception as e:
                log_lines.append(f"⚠️ Eroare batch {i//500+1}: {str(e)[:50]}")
                with log_container:
                    log_display.text('\n'.join(log_lines))

                # Retry individual
                for item in batch:
                    try:
                        supabase_client.table('woocommerce_stock').upsert([item]).execute()
                        saved += 1
                    except:
                        failed_saves += 1

        end_time = datetime.now()
        duration = (end_time - start_time).seconds

        log_lines.append(f"✅ STEP 4: {saved} produse salvate ({failed_saves} eșuate)")
        log_lines.append(f"🏁 Finalizat în {duration}s ({duration//60}m {duration%60}s)")
        with log_container:
            log_display.text('\n'.join(log_lines))

        with progress_container:
            progress_bar.progress(1.0)
            time.sleep(0.3)

        progress_container.empty()

        # REZULTAT FINAL
        with result_container:
            st.subheader("✅ Sincronizare Completă!")
            st.success(f"🎉 {saved} produse salvate în {duration//60}m {duration%60}s")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📦 Produse totale", len(all_items))
            col2.metric("💾 Salvate", saved)
            col3.metric("🔄 SKU-uri unice", len(sku_map))
            col4.metric("⏱️ Timp", f"{duration//60}m {duration%60}s")

            if failed_saves > 0:
                st.warning(f"⚠️ {failed_saves} produse eșuate")

            if duplicate_details:
                st.markdown("---")
                st.warning(f"⚠️ {len(duplicate_details)} SKU-uri duplicate detectate")
                with st.expander("📋 Vezi detalii duplicate"):
                    st.json(duplicate_details[:20])

        return True

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).seconds

        log_lines.append(f"❌ EROARE după {duration}s: {str(e)}")
        with log_container:
            log_display.text('\n'.join(log_lines))

        progress_container.empty()

        with result_container:
            st.subheader("❌ Sincronizare Eșuată")
            st.error(f"💥 Eroare după {duration//60}m {duration%60}s")
            st.error(str(e))
            with st.expander("📋 Traceback complet"):
                st.code(traceback.format_exc())

        return False

def get_woocommerce_stock_from_supabase(supabase_client):
    """Citește toate stocurile din Supabase"""
    try:
        all_data = []
        offset = 0
        batch_size = 1000

        while True:
            result = supabase_client.table('woocommerce_stock').select('*').range(offset, offset + batch_size - 1).execute()
            if not result.data:
                break
            all_data.extend(result.data)
            offset += batch_size
            if len(result.data) < batch_size:
                break

        return {
            row['sku']: {
                'stock': float(row.get('stock_quantity', 0)),
                'status': row.get('stock_status', 'outofstock')
            }
            for row in all_data
        }
    except Exception as e:
        st.error(f"Eroare citire Supabase: {e}")
        return {}

def get_smartbill_stocks(email, token, cif, warehouse_name):
    """Preluare stocuri din SmartBill"""
    try:
        r = requests.get(
            "https://ws.smartbill.ro/SBORO/api/stocks",
            auth=HTTPBasicAuth(email, token),
            headers={"Accept": "application/json"},
            params={
                "cif": cif,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "warehouseName": warehouse_name
            },
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
            sb_dict[code] = {
                'name': p.get('productName', ''),
                'stock': float(p.get('quantity', 0))
            }

    return sb_dict

def generate_discrepancy_report(sb_dict, woo_dict):
    """Generare raport discrepanțe"""
    disc = []

    # Produse în SmartBill dar nu în WooCommerce
    for code, sb in sb_dict.items():
        if code not in woo_dict and sb['stock'] > 0:
            disc.append({
                'SKU': code,
                'Denumire': sb['name'][:60],
                'Stoc SB': float(sb['stock']),
                'Stoc Woo': 0.0,
                'Diferență': float(sb['stock']),
                'Tip': 'Lipsă în Woo',
                'Status': 'CRITIC',
                'Prioritate': 1
            })

    # Produse cu stoc în SmartBill dar 0 în WooCommerce
    for code, sb in sb_dict.items():
        if code in woo_dict and sb['stock'] > 0 and woo_dict[code]['stock'] == 0:
            disc.append({
                'SKU': code,
                'Denumire': sb['name'][:60],
                'Stoc SB': float(sb['stock']),
                'Stoc Woo': 0.0,
                'Diferență': float(sb['stock']),
                'Tip': 'Stoc 0 în Woo',
                'Status': 'ATENȚIE',
                'Prioritate': 2
            })

    # Diferențe de stoc
    for code in set(sb_dict.keys()) & set(woo_dict.keys()):
        sb_stock = sb_dict[code]['stock']
        woo_stock = woo_dict[code]['stock']
        diff = sb_stock - woo_stock

        if abs(diff) > 0.01 and sb_stock > 0:
            disc.append({
                'SKU': code,
                'Denumire': sb_dict[code]['name'][:60],
                'Stoc SB': float(sb_stock),
                'Stoc Woo': float(woo_stock),
                'Diferență': round(float(diff), 2),
                'Tip': 'Diferență',
                'Status': 'SYNC',
                'Prioritate': 3
            })

    # Produse în WooCommerce dar nu în SmartBill
    for code, woo in woo_dict.items():
        if code not in sb_dict and woo['stock'] > 0:
            disc.append({
                'SKU': code,
                'Denumire': '',
                'Stoc SB': 0.0,
                'Stoc Woo': float(woo['stock']),
                'Diferență': -float(woo['stock']),
                'Tip': 'În Woo nu în SB',
                'Status': 'VERIFICARE',
                'Prioritate': 4
            })

    df = pd.DataFrame(disc)
    if len(df) > 0:
        df = df.sort_values(['Prioritate', 'Stoc SB'], ascending=[True, False])
        df = df.drop('Prioritate', axis=1)
        df['Stoc SB'] = df['Stoc SB'].astype(float)
        df['Stoc Woo'] = df['Stoc Woo'].astype(float)
        df['Diferență'] = df['Diferență'].astype(float)

    return df

# ═══════════════════════════════════════════════════════════════════════════
# UI PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

st.title("📦 Verificare Stoc: SmartBill vs WooCommerce")
st.caption("Versiune POST-MIGRARE SUPABASE (2025-11-19)")
st.markdown("---")

# Informații bază de date
if supabase:
    try:
        count_result = supabase.table('woocommerce_stock').select('*', count='exact').limit(1).execute()
        total = count_result.count if hasattr(count_result, 'count') else 0

        result = supabase.table('woocommerce_stock').select('last_synced_at').order('last_synced_at', desc=True).limit(1).execute()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("📦 Produse în baza de date", total)
        with col2:
            if result.data:
                last_sync = result.data[0]['last_synced_at']
                st.info(f"📅 Ultima sincronizare: {last_sync} (UTC)")
            else:
                st.info("📅 Nicio sincronizare încă")
    except Exception as e:
        st.error(f"⚠️ Eroare citire info: {e}")

st.markdown("---")

# Butoane acțiuni principale
c1, c2, c3 = st.columns(3)

with c1:
    quick = st.button("⚡ Update Rapid Stocuri", type="primary", use_container_width=True)

with c2:
    full = st.button("🔄 Sincronizare Completă", type="secondary", use_container_width=True)

with c3:
    report = st.button("📊 Raport Discrepanțe", type="secondary", use_container_width=True)

# Acțiuni
if quick:
    if not supabase or not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Configurează toate serviciile!")
    else:
        update_stocks_only(woo_url, woo_key, woo_secret, supabase)

if full:
    if not supabase or not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Configurează toate serviciile!")
    else:
        sync_woocommerce_full(woo_url, woo_key, woo_secret, supabase)

if report:
    if not supabase or not all([sb_email, sb_token, sb_cif]):
        st.error("⚠️ Configurează SmartBill și Supabase!")
    else:
        st.markdown("---")
        st.subheader("📊 Generare Raport Discrepanțe")

        with st.spinner("📥 Preluare date WooCommerce din Supabase..."):
            woo_dict = get_woocommerce_stock_from_supabase(supabase)

        with st.spinner("📥 Preluare stocuri SmartBill..."):
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

                # Metrici
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🔴 CRITIC", len(df[df['Status'] == 'CRITIC']))
                m2.metric("🟡 ATENȚIE", len(df[df['Status'] == 'ATENȚIE']))
                m3.metric("🔵 SYNC", len(df[df['Status'] == 'SYNC']))
                m4.metric("📝 Total", len(df))

                st.markdown("---")

                # Filtre
                f1, f2 = st.columns([1, 2])
                with f1:
                    status_filter = st.multiselect(
                        "Filtrează după Status",
                        df['Status'].unique(),
                        df['Status'].unique()
                    )
                with f2:
                    search = st.text_input("🔎 Caută SKU sau Denumire")

                # Aplicare filtre
                df_filtered = df[df['Status'].isin(status_filter)]

                if search:
                    df_filtered = df_filtered[
                        df_filtered['SKU'].astype(str).str.contains(search, case=False, na=False) |
                        df_filtered['Denumire'].astype(str).str.contains(search, case=False, na=False)
                    ]

                # Afișare tabel
                st.dataframe(
                    df_filtered,
                    use_container_width=True,
                    height=450,
                    hide_index=True
                )

                st.caption(f"Afișate {len(df_filtered)} din {len(df)} discrepanțe")

                # Export CSV
                csv = df_filtered.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    "📥 Descarcă CSV",
                    csv,
                    f"raport_discrepante_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    "text/csv"
                )
            else:
                st.success("🎉 Nu există discrepanțe! Totul este sincronizat corect!")
                st.balloons()
        else:
            st.error("❌ Nu s-au putut prelua datele. Verifică configurările!")

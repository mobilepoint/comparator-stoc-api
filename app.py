"""
Aplicație Streamlit - Verificare Stoc SmartBill vs WooCommerce
VERSIUNE STABILĂ - cu error handling complet
"""

import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import time
import traceback

st.set_page_config(
    page_title="Verificare Stoc SmartBill vs WooCommerce",
    page_icon="📦",
    layout="wide"
)

WAREHOUSE_NAME = "Eroilor 19 cv"

# ====================== SIDEBAR ======================

with st.sidebar:
    st.header("⚙️ Configurări")
    
    st.subheader("🔵 SmartBill")
    try:
        sb_email = st.secrets["smartbill"]["email"]
        sb_token = st.secrets["smartbill"]["token"]
        sb_cif = st.secrets["smartbill"]["cif"]
        st.success("✅ SmartBill")
    except:
        sb_email = st.text_input("Email", value="mobilepointgsm@gmail.com")
        sb_token = st.text_input("Token", type="password")
        sb_cif = st.text_input("CIF", value="RO36898183")
    
    st.markdown("---")
    
    st.subheader("🟢 WooCommerce")
    try:
        woo_url = st.secrets["woocommerce"]["url"]
        woo_key = st.secrets["woocommerce"]["consumer_key"]
        woo_secret = st.secrets["woocommerce"]["consumer_secret"]
        st.success("✅ WooCommerce")
    except:
        woo_url = st.text_input("URL", value="https://servicepack.ro")
        woo_key = st.text_input("Consumer Key", type="password")
        woo_secret = st.text_input("Consumer Secret", type="password")
    
    st.markdown("---")
    
    st.subheader("💾 Supabase")
    try:
        supabase_url = st.secrets["supabase"]["url"]
        supabase_key = st.secrets["supabase"]["key"]
        supabase: Client = create_client(supabase_url, supabase_key)
        st.success("✅ Conectat")
    except:
        supabase_url = st.text_input("Supabase URL")
        supabase_key = st.text_input("Supabase Key", type="password")
        if supabase_url and supabase_key:
            try:
                supabase = create_client(supabase_url, supabase_key)
                st.success("✅ Conectat")
            except Exception as e:
                st.error(f"❌ Eroare: {e}")
                supabase = None
        else:
            supabase = None

# ====================== FUNCȚII ======================

def update_stocks_only(woo_url, woo_key, woo_secret, supabase_client):
    """Update rapid stocuri - TOATE SKU-urile din DB"""
    st.markdown("---")
    st.subheader("⚡ Update Rapid Stocuri")
    
    progress_container = st.container()
    
    try:
        with progress_container:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Citește TOATE SKU-urile din DB (fără limit)
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
                    status_text.text(f"📥 Citit {len(existing_skus)} SKU-uri din DB...")
                    
                    if len(result.data) < batch_size:
                        break
                        
                except Exception as e:
                    st.error(f"Eroare citire DB: {e}")
                    break
            
            st.info(f"📦 {len(existing_skus)} SKU-uri în baza de date")
            progress_bar.progress(0.2)
            
            # Preluare stocuri din WooCommerce
            status_text.text("📥 Preluare stocuri din WooCommerce...")
            
            stock_dict = {}
            page = 1
            endpoint = f"{woo_url}/wp-json/wc/v3/products"
            
            while True:
                try:
                    response = requests.get(
                        endpoint,
                        auth=(woo_key, woo_secret),
                        params={"per_page": 100, "page": page, "status": "publish", "_fields": "sku,stock_quantity,stock_status"},
                        timeout=30
                    )
                    
                    if response.status_code != 200:
                        st.warning(f"Status {response.status_code} la pagina {page}")
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
                                'last_synced_at': datetime.now().isoformat()
                            }
                    
                    status_text.text(f"📥 {len(stock_dict)} stocuri preluate (pagina {page})...")
                    page += 1
                    time.sleep(0.1)
                    
                except Exception as e:
                    st.error(f"Eroare WooCommerce pagina {page}: {e}")
                    break
            
            stock_updates = list(stock_dict.values())
            progress_bar.progress(0.8)
            
            if stock_updates:
                status_text.text(f"💾 Actualizare {len(stock_updates)} stocuri...")
                updated = 0
                
                for i in range(0, len(stock_updates), 500):
                    batch = stock_updates[i:i+500]
                    try:
                        supabase_client.table('woocommerce_stock').upsert(batch).execute()
                        updated += len(batch)
                        status_text.text(f"💾 {updated}/{len(stock_updates)}...")
                    except Exception as e:
                        st.warning(f"Batch {i//500+1} eșuat, încerc individual...")
                        for item in batch:
                            try:
                                supabase_client.table('woocommerce_stock').upsert([item]).execute()
                                updated += 1
                            except:
                                pass
                
                progress_bar.progress(1.0)
                time.sleep(0.5)
                progress_bar.empty()
                status_text.empty()
                
                st.success(f"✅ {updated} din {len(stock_updates)} stocuri actualizate")
                
                if updated < len(stock_updates):
                    st.warning(f"⚠️ {len(stock_updates) - updated} stocuri nu au putut fi actualizate")
                
                return True
            else:
                st.warning("Nu s-au găsit stocuri de actualizat")
                return False
                
    except Exception as e:
        st.error(f"❌ EROARE CRITICĂ: {e}")
        st.code(traceback.format_exc())
        return False

def sync_woocommerce_full(woo_url, woo_key, woo_secret, supabase_client):
    """Sync complet cu error handling robust"""
    st.markdown("---")
    st.subheader("🔄 Sincronizare Completă")
    
    sync_container = st.container()
    
    try:
        with sync_container:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # STEP 1: Preluare produse simple și variabile
            status_text.text("📥 Preluare produse...")
            all_items = []
            page = 1
            endpoint = f"{woo_url}/wp-json/wc/v3/products"
            
            products_data = []
            while True:
                try:
                    response = requests.get(
                        endpoint,
                        auth=(woo_key, woo_secret),
                        params={"per_page": 100, "page": page, "status": "publish"},
                        timeout=30
                    )
                    
                    if response.status_code != 200:
                        st.warning(f"Status {response.status_code} la pagina {page}")
                        break
                    
                    products = response.json()
                    if not products:
                        break
                    
                    products_data.extend(products)
                    status_text.text(f"📥 {len(products_data)} produse (pagina {page})...")
                    page += 1
                    time.sleep(0.1)
                    
                except Exception as e:
                    st.error(f"Eroare pagina {page}: {e}")
                    break
            
            progress_bar.progress(0.3)
            
            simple = [p for p in products_data if p.get('type') in ['simple', 'external', 'grouped']]
            variable = [p for p in products_data if p.get('type') == 'variable']
            
            st.info(f"📦 Simple: {len(simple)} | Variabile: {len(variable)}")
            all_items.extend(simple)
            
            # STEP 2: Preluare variații
            if variable:
                status_text.text("🔄 Preluare variații...")
                total_var = 0
                failed_var = 0
                
                for idx, vp in enumerate(variable, 1):
                    vpage = 1
                    
                    while True:
                        try:
                            vr = requests.get(
                                f"{woo_url}/wp-json/wc/v3/products/{vp['id']}/variations",
                                auth=(woo_key, woo_secret),
                                params={"per_page": 100, "page": vpage},
                                timeout=30
                            )
                            
                            if vr.status_code != 200:
                                failed_var += 1
                                break
                            
                            vlist = vr.json()
                            if not vlist:
                                break
                            
                            all_items.extend(vlist)
                            total_var += len(vlist)
                            vpage += 1
                            time.sleep(0.05)
                            
                        except Exception as e:
                            failed_var += 1
                            break
                    
                    if idx % 20 == 0 or idx == len(variable):
                        status_text.text(f"🔄 {idx}/{len(variable)} produse ({total_var} variații)")
                        progress_bar.progress(0.3 + (0.4 * (idx / len(variable))))
                
                if failed_var > 0:
                    st.warning(f"⚠️ {failed_var} produse variabile au eșuat la preluare variații")
            
            progress_bar.progress(0.7)
            st.success(f"✅ {len(all_items)} produse preluate total")
            
            # STEP 3: Procesare și deduplicare
            status_text.text("💾 Procesare și deduplicare...")
            
            sku_map = {}
            duplicates_count = 0
            no_sku_count = 0
            
            for item in all_items:
                sku = item.get('sku', '').strip()
                
                if not sku:
                    no_sku_count += 1
                    continue
                
                if sku in sku_map:
                    duplicates_count += 1
                
                sku_map[sku] = {
                    'id': item.get('id'),
                    'name': item.get('name', ''),
                    'type': item.get('type', 'unknown'),
                    'stock': item.get('stock_quantity'),
                    'status': item.get('stock_status', 'outofstock')
                }
            
            if duplicates_count > 0:
                st.warning(f"⚠️ {duplicates_count} SKU-uri duplicate eliminate")
            
            if no_sku_count > 0:
                st.info(f"ℹ️ {no_sku_count} produse fără SKU (ignorate)")
            
            progress_bar.progress(0.8)
            
            # STEP 4: Pregătire date pentru salvare
            stock_data = []
            new_products = []
            
            for sku, prod in sku_map.items():
                stock_data.append({
                    'sku': sku,
                    'stock_quantity': float(prod['stock']) if prod['stock'] is not None else 0,
                    'stock_status': prod['status'],
                    'product_type': prod['type'],
                    'woo_product_id': prod['id'],
                    'last_synced_at': datetime.now().isoformat()
                })
                
                new_products.append({
                    'sku': sku,
                    'name': prod['name'],
                    'name_norm': prod['name'].lower().strip()
                })
            
            # STEP 5: Verifică produse noi pentru catalog
            try:
                existing_skus = set()
                offset = 0
                batch_size = 1000
                
                while True:
                    result = supabase_client.schema('catalog').table('product_sku').select('sku').range(offset, offset + batch_size - 1).execute()
                    
                    if not result.data:
                        break
                    
                    for row in result.data:
                        existing_skus.add(row['sku'])
                    
                    offset += batch_size
                    
                    if len(result.data) < batch_size:
                        break
                        
            except Exception as e:
                st.warning(f"Nu am putut citi catalog: {e}")
                existing_skus = set()
            
            truly_new = [p for p in new_products if p['sku'] not in existing_skus]
            
            if truly_new:
                status_text.text(f"📝 Inserare {len(truly_new)} produse noi în catalog...")
                inserted = 0
                
                for i in range(0, len(truly_new), 50):
                    batch = truly_new[i:i+50]
                    try:
                        pdata = [{'name': p['name'], 'name_norm': p['name_norm']} for p in batch]
                        res = supabase_client.schema('catalog').table('product').insert(pdata).execute()
                        
                        if res.data:
                            for idx, row in enumerate(res.data):
                                try:
                                    supabase_client.schema('catalog').table('product_sku').insert({
                                        'product_id': row['id'],
                                        'sku': batch[idx]['sku'],
                                        'is_primary': True
                                    }).execute()
                                    inserted += 1
                                except:
                                    pass
                    except Exception as e:
                        st.warning(f"Eroare insert produse noi: {e}")
                
                if inserted > 0:
                    st.success(f"✅ {inserted} produse noi adăugate în catalog")
            
            progress_bar.progress(0.9)
            
            # STEP 6: Salvare stocuri
            status_text.text(f"💾 Salvare {len(stock_data)} stocuri...")
            upserted = 0
            failed = 0
            
            for i in range(0, len(stock_data), 500):
                batch = stock_data[i:i+500]
                try:
                    supabase_client.table('woocommerce_stock').upsert(batch).execute()
                    upserted += len(batch)
                    status_text.text(f"💾 {upserted}/{len(stock_data)}...")
                except Exception as e:
                    st.warning(f"Batch {i//500+1} eșuat, încerc individual...")
                    for item in batch:
                        try:
                            supabase_client.table('woocommerce_stock').upsert([item]).execute()
                            upserted += 1
                        except:
                            failed += 1
            
            progress_bar.progress(1.0)
            time.sleep(0.5)
            progress_bar.empty()
            status_text.empty()
            
            st.success(f"✅ SINCRONIZARE COMPLETĂ!")
            st.info(f"📊 {upserted} stocuri salvate" + (f" ({failed} eșuate)" if failed > 0 else ""))
            
            return True
            
    except Exception as e:
        st.error(f"❌ EROARE CRITICĂ LA SINCRONIZARE: {e}")
        st.code(traceback.format_exc())
        return False

def get_woocommerce_stock_from_supabase(supabase_client):
    """Citește TOATE stocurile din Supabase"""
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
        
        return {row['sku']: {'stock': float(row.get('stock_quantity', 0)), 'status': row.get('stock_status', 'outofstock')} for row in all_data}
        
    except Exception as e:
        st.error(f"Eroare citire Supabase: {e}")
        return {}

def get_smartbill_stocks(email, token, cif, warehouse_name):
    """Preia stocuri SmartBill"""
    try:
        r = requests.get(
            "https://ws.smartbill.ro/SBORO/api/stocks",
            auth=HTTPBasicAuth(email, token),
            headers={"Accept": "application/json"},
            params={"cif": cif, "date": datetime.now().strftime("%Y-%m-%d"), "warehouseName": warehouse_name},
            timeout=30
        )
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        st.error(f"Eroare SmartBill: {e}")
        return None

def process_smartbill_data(data):
    """Procesează SmartBill"""
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
    """Generează raport discrepanțe"""
    disc = []
    for code, sb in sb_dict.items():
        if code not in woo_dict and sb['stock'] > 0:
            disc.append({'SKU': code, 'Denumire': sb['name'], 'Stoc SB': sb['stock'], 'Stoc Woo': 'N/A', 'Dif': sb['stock'], 'Tip': '❌ Lipsă Woo', 'Status': 'CRITIC', 'P': 1})
        elif code in woo_dict and sb['stock'] > 0 and woo_dict[code]['stock'] == 0:
            disc.append({'SKU': code, 'Denumire': sb['name'], 'Stoc SB': sb['stock'], 'Stoc Woo': 0, 'Dif': sb['stock'], 'Tip': '⚠️ 0 Woo', 'Status': 'ATENTIE', 'P': 2})
    for code in set(sb_dict.keys()) & set(woo_dict.keys()):
        diff = sb_dict[code]['stock'] - woo_dict[code]['stock']
        if abs(diff) > 0.01:
            disc.append({'SKU': code, 'Denumire': sb_dict[code]['name'], 'Stoc SB': sb_dict[code]['stock'], 'Stoc Woo': woo_dict[code]['stock'], 'Dif': round(diff, 2), 'Tip': '🔄 Diferență', 'Status': 'SYNC', 'P': 3})
    for code, woo in woo_dict.items():
        if code not in sb_dict and woo['stock'] > 0:
            disc.append({'SKU': code, 'Denumire': 'N/A', 'Stoc SB': 0, 'Stoc Woo': woo['stock'], 'Dif': -woo['stock'], 'Tip': '🚫 În Woo nu SB', 'Status': 'CRITIC', 'P': 1})
    df = pd.DataFrame(disc)
    if len(df) > 0:
        df = df.sort_values(['P', 'Stoc SB'], ascending=[True, False]).drop('P', axis=1)
    return df

# ====================== UI ======================

st.title("📦 Stoc: SmartBill vs WooCommerce")
st.markdown("---")

# Info stats
if supabase:
    try:
        # Count total în DB
        count_result = supabase.table('woocommerce_stock').select('*', count='exact').limit(1).execute()
        total_in_db = count_result.count if hasattr(count_result, 'count') else 0
        
        # Last sync
        result = supabase.table('woocommerce_stock').select('last_synced_at').order('last_synced_at', desc=True).limit(1).execute()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("📦 Produse în DB", total_in_db)
        with col2:
            if result.data:
                st.info(f"📅 Ultima sync: {result.data[0]['last_synced_at']}")
    except:
        pass

st.markdown("---")

c1, c2, c3 = st.columns(3)

with c1:
    quick = st.button("⚡ Update Rapid", type="primary", use_container_width=True, help="Actualizează stocuri pentru produse existente")
with c2:
    full = st.button("🔄 Sync Complet", type="secondary", use_container_width=True, help="Preluare completă produse + variații")
with c3:
    report = st.button("📊 Raport", type="secondary", use_container_width=True, help="Compară SmartBill vs WooCommerce")

if quick:
    if not supabase or not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Configurează credențialele!")
    else:
        update_stocks_only(woo_url, woo_key, woo_secret, supabase)

if full:
    if not supabase or not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Configurează credențialele!")
    else:
        sync_woocommerce_full(woo_url, woo_key, woo_secret, supabase)

if report:
    if not supabase or not all([sb_email, sb_token, sb_cif]):
        st.error("⚠️ Configurează credențialele!")
    else:
        st.markdown("---")
        st.subheader("📊 Generare Raport")
        
        with st.spinner("📥 Preluare date WooCommerce din Supabase..."):
            woo_dict = get_woocommerce_stock_from_supabase(supabase)
        
        with st.spinner("📥 Preluare date SmartBill..."):
            sb_data = get_smartbill_stocks(sb_email, sb_token, sb_cif, WAREHOUSE_NAME)
        
        if woo_dict and sb_data:
            sb_dict = process_smartbill_data(sb_data)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("📦 WooCommerce (din DB)", len(woo_dict))
            with col2:
                st.metric("📦 SmartBill (live)", len(sb_dict))
            
            df = generate_discrepancy_report(sb_dict, woo_dict)
            
            if len(df) > 0:
                st.markdown("---")
                st.header("📊 Raport Discrepanțe")
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🔴 Critice", len(df[df['Status'] == 'CRITIC']))
                m2.metric("🟡 Atenție", len(df[df['Status'] == 'ATENTIE']))
                m3.metric("🔵 Sincronizare", len(df[df['Status'] == 'SYNC']))
                m4.metric("📝 Total", len(df))
                
                st.markdown("---")
                
                f1, f2 = st.columns([1, 2])
                with f1:
                    status_filter = st.multiselect("Filtrează status", df['Status'].unique(), df['Status'].unique())
                with f2:
                    search = st.text_input("🔎 Caută SKU sau denumire")
                
                df_filt = df[df['Status'].isin(status_filter)]
                if search:
                    df_filt = df_filt[
                        df_filt['SKU'].astype(str).str.contains(search, case=False, na=False) |
                        df_filt['Denumire'].astype(str).str.contains(search, case=False, na=False)
                    ]
                
                st.dataframe(df_filt, use_container_width=True, height=450, hide_index=True)
                st.caption(f"Afișate {len(df_filt)} din {len(df)} discrepanțe")
                
                csv = df_filt.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 Descarcă CSV", csv, f"raport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", use_container_width=True)
            else:
                st.success("🎉 Nu există discrepanțe!")
                st.balloons()
        else:
            if not woo_dict:
                st.error("❌ Nu s-au putut citi datele WooCommerce din Supabase")
            if not sb_data:
                st.error("❌ Nu s-au putut prelua datele SmartBill")

from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
import time
import csv
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraping.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configured Chrome options to reduce SSL errors
chrome_options = Options()
chrome_options.add_argument("--ignore-ssl-errors-yes")
chrome_options.add_argument("--ignore-certificate-errors")
chrome_options.add_argument("--disable-web-security")
chrome_options.add_argument("--allow-running-insecure-content")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--log-level=3")
# Blocks some  ads (not all)  to prevent click interception
chrome_options.add_argument("--disable-popup-blocking")
chrome_options.add_experimental_option("prefs", {
    "profile.default_content_setting_values.notifications": 2,
    "profile.default_content_settings.popups": 0,
    "profile.managed_default_content_settings.images": 2
})

# Set page load strategy
chrome_options.page_load_strategy = 'eager'

driver = Chrome(options=chrome_options)

# Set timeouts
driver.set_page_load_timeout(20)
driver.implicitly_wait(5)

def scroll(direction = "down"):
    if direction == "down":    
        logger.info("Scrolling to bottom of page...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        logger.info("Scrolling completed")
    elif direction == "up":
        logger.info("Scrolling back to top...")
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        logger.info("Scrolling completed")

def scrape_facility_details(url):
    """Scrape details from individual facility page"""
    try:
        logger.info(f"Scraping: {url}")
        driver.get(url)
        time.sleep(2)
        
        facility_data = {}
        
        # Get business name 
        try:
            h1_element = driver.find_element(By.XPATH, "//h1[@class='back-to noprint']")
            full_text = h1_element.text
            business_name = full_text.split(" - ")[0].strip().replace('\ufeff', '')
            facility_data['business_name'] = business_name
        except:
            facility_data['business_name'] = "N/A"
        
        # Get address 
        try:
            address_elements = driver.find_elements(By.XPATH, "//div[@class='contact']//p[@class='addr']")
            address_parts = [addr.text.replace('\ufeff', '') for addr in address_elements]
            address = ", ".join(address_parts) if address_parts else "N/A"
            facility_data['address'] = address
        except:
            facility_data['address'] = "N/A"
        
        # Get materials accepted 
        try:
            materials = driver.find_elements(By.XPATH, "//tr[@class=' odd' or @class=' even']//td[@class='material-name']")
            materials_list = [material.text.replace('\ufeff', '') for material in materials]
            facility_data['materials'] = ", ".join(materials_list)
        except:
            facility_data['materials'] = "N/A"
        
        # Get last updated date 
        try:
            last_updated = driver.find_element(By.XPATH, "//h1[@class='back-to noprint']//span[@class='last-verified']").text.replace('\ufeff', '')
            facility_data['last_updated'] = last_updated
        except:
            facility_data['last_updated'] = "N/A"
        
        logger.info(f"Successfully scraped: {facility_data['business_name']}")
        return facility_data
        
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return None

def safe_click_pagination(page_num):
    #this fucntion is basically the ads will interuppt in between so its used to handle errors
    try:
        # Method 1: Try normal click
        page_link = driver.find_element(By.XPATH, f"//a[normalize-space()='{page_num}']")
        page_link.click()
        return True
    except ElementClickInterceptedException:
        try:
            # Method 2: JavaScript click
            page_link = driver.find_element(By.XPATH, f"//a[normalize-space()='{page_num}']")
            driver.execute_script("arguments[0].click();", page_link)
            return True
        except:
            try:
                # Method 3: Navigate directly by URL
                current_url = driver.current_url
                if "&page=" in current_url:
                    new_url = current_url.split("&page=")[0] + f"&page={page_num}"
                else:
                    new_url = current_url + f"&page={page_num}"
                driver.get(new_url)
                return True
            except:
                return False
    except:
        return False

try:
    logger.info("Loading page...")
    driver.get("https://search.earth911.com/")
    driver.maximize_window()
    logger.info("Page loaded successfully")
    
    # Scroll to bottom of page
    scroll()
    
    # Scroll back to top
    scroll("up")
    
    # Check if popup exists
    wait = WebDriverWait(driver, 15)
    try:
        popup = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@class='_form-content']")))
        if popup:
            logger.info("Popup exists, looking for close button...")
            close_button = driver.find_element(By.XPATH, "//div[@class='_close']")
            close_button.click()
            logger.info("popup closed")
            time.sleep(2)
    except TimeoutException:
        logger.info("No popup found")
        
    # Fill search form
    search_For = driver.find_element(By.XPATH, "//input[@id='what']")
    search_For.send_keys("Electronics")
    
    zip_code = driver.find_element(By.XPATH, "//input[@id='where']")
    zip_code.send_keys("10001")
    
    driver.find_element(By.XPATH, "//input[@id='submit-location-search']").click()
    time.sleep(3)
    
    # Handle the distance dropdown
    try:
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[@class='result-range']")))
        
        distance_select = driver.find_element(By.XPATH, "//div[@class='result-range']//select")
        select = Select(distance_select)
        select.select_by_visible_text("100 miles")
        logger.info("Selected 100 miles from dropdown")
        time.sleep(3)

        facilities_links = []
        
        # Get total pages
        scroll()
        try:
            pages = driver.find_elements(By.XPATH, "//div[@class='pager noprint']//a")
            if pages:
                total_pages = int(pages[-2].text) if len(pages) > 1 else 1
            else:
                total_pages = 1
        except:
            total_pages = 1
            
        logger.info(f"Total pages found: {total_pages}")
        
        # Scrape first page
        res_list = driver.find_element(By.XPATH,"//ul[@class='result-list']")
        all_li = res_list.find_elements(By.XPATH, ".//li[contains(@class, 'result-item location even') or contains(@class, 'result-item location odd')]")
        for li in all_li:
            try:
                title_link = li.find_element(By.XPATH, ".//h2[@class='title']/a").get_attribute("href")
                facilities_links.append(title_link)
            except:
                continue
        logger.info(f"Page 1 completed - {len(facilities_links)} links found")
        
        # Scrape remaining and limit to 5 pages to avoid too much data
        for pg_num in range(2, 6):
            logger.info(f"Navigating to page {pg_num}")
            
            if safe_click_pagination(pg_num):
                time.sleep(3)
                
                try:
                    res_list = driver.find_element(By.XPATH,"//ul[@class='result-list']")
                    all_li = res_list.find_elements(By.XPATH, ".//li[contains(@class, 'result-item location even') or contains(@class, 'result-item location odd')]")
                    page_links = []
                    for li in all_li:
                        try:
                            title_link = li.find_element(By.XPATH, ".//h2[@class='title']/a").get_attribute("href")
                            facilities_links.append(title_link)
                            page_links.append(title_link)
                        except:
                            continue
                    logger.info(f"Page {pg_num} completed - {len(page_links)} links found")
                except Exception as e:
                    logger.error(f"Error scraping page {pg_num}: {e}")
            else:
                logger.warning(f"Failed to navigate to page {pg_num}")
                break
        
        logger.info(f"Total links collected: {len(facilities_links)}")
        
        #after getting all links we are processing each one by one and extract data
        all_facilities_data = []
        for i, link in enumerate(facilities_links[:20], 1):
            logger.info(f"Scraping facility {i}/{len(facilities_links[:20])}")
            facility_data = scrape_facility_details(link)
            if facility_data:
                all_facilities_data.append(facility_data)
            time.sleep(1)
        
        # Save to CSV
        if all_facilities_data:
            with open('facilities_data.csv', 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['business_name', 'address', 'materials', 'last_updated']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_facilities_data)
            logger.info(f"Data saved to facilities_data.csv with {len(all_facilities_data)} facilities")

    except Exception as e:
        logger.error(f"Error handling distance dropdown: {e}")
        
except TimeoutException:
    logger.error("Page load timeout - the page took too long to load")
except Exception as e:
    logger.error(f"An error occurred: {e}")
finally:
    logger.info("Closing driver...")
    driver.quit()
    logger.info("Driver closed")

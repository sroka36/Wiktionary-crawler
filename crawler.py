import requests
from bs4 import BeautifulSoup
import argparse
import sys
import json

def get_character_data(character):
    
    # 1. Fetch URL and set headers for hiding it is crawler.
    url = f"https://en.wiktionary.org/wiki/{character}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        # Check if it works successfully.
        response.raise_for_status()
        with open('debug.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching page for {character}: {e}", file=sys.stderr)
        return None

    # 2. Parse HTML
    soup = BeautifulSoup(response.content, 'html.parser')

    data = {
        'character': character,
        'cangjie': None,
        'mandarin': None,
        'middle_chinese': {
            'baxter_sagart': None,
            'zhengzhang_shangfang': None
        },
        'old_chinese': {
             'zhengzhang_shangfang': None
        },
        'japanese_readings': {
            'goon': None,
            'kanon': None,
            'toon': None
        }
    }

    # 3. Get Cangjie
    cangjie_link = soup.select_one('a[title="Appendix:Chinese Cangjie"]')
    if cangjie_link:
        container = cangjie_link.find_parent(['p', 'div', 'tr'])
        if container:
            target_span = container.select_one('span.Hani')
            if target_span:
                data['cangjie'] = target_span.get_text(strip=True)

    # 4. Find Chinese section
    chinese_content = []
    chinese_h2 = None
    for h2 in soup.find_all('h2'):
        if 'Chinese' in h2.get_text():
            chinese_h2 = h2
            break
            
    
    if chinese_h2:
        # Determine start node for traversal
        # In modern MediaWiki, h2 might be wrapped in div.mw-heading
        start_node = chinese_h2
        if chinese_h2.parent and 'mw-heading' in chinese_h2.parent.get('class', []):
            start_node = chinese_h2.parent
            
        curr = start_node.next_sibling
        while curr:
            # Stop if we hit the next h2 (or its wrapper)
            if curr.name == 'h2': 
                break
            if curr.name == 'div' and 'mw-heading' in curr.get('class', []):
                # Check if it's an h2 wrapper
                if curr.find('h2'):
                    break
            
            chinese_content.append(curr)
            curr = curr.next_sibling

    def search_in_chinese(query, class_name=None):
        # Search within gathered chinese content nodes
        for node in chinese_content:
            if not isinstance(node, str) and node.name: # Skip nav strings
                # Search recursively in this node
                # Find element containing query text
                matches = node.find_all(string=lambda t: t and query in t)
                for match in matches:
                    # Look for the target data
                    # logic: find 'zhpron-monospace' nearby
                    
                    # 1. Check inside the same li if match is in li
                    li = match.find_parent('li')
                    if li:
                        target = li.find(class_=class_name) if class_name else None
                        if target: return target.get_text(strip=True)
                        
                        # 2. Check dl sibling (common for Mandarin)
                        # e.g. <ul><li>Mandarin</li></ul><dl><dd>...</dd></dl>
                        ul = li.find_parent('ul')
                        if ul:
                            next_el = ul.find_next_sibling()
                            while next_el: 
                                if next_el.name in ['ul', 'h3', 'h4', 'h5', 'p', 'div'] and next_el.name != 'dl':
                                     # Don't skip too far, stopping at other blocks
                                     # But sometimes there are P between UL and DL?
                                     # Let's strictly look for DL or nothing
                                     if next_el.name == 'dl': break
                                     # If it's another list or header, stop
                                     pass
                                
                                if next_el.name == 'dl':
                                    target = next_el.find(class_=class_name)
                                    if target: 
                                        return target.get_text(strip=True)
                                    break # Found DL but no target?
                                
                                next_el = next_el.next_sibling
                                
                    # 3. Just search next element with class
                    # Be careful not to pick up other dialects
                    pass
        return None

    # 2. Mandarin
    # We gathered chinese_content, let's process it more robustly
    # We need to find the specific "Pronunciation" subsection if possible, but searching for "Mandarin" + "zhpron-monospace" usually works uniquely enough.
    
    # Specific logic for Mandarin:
    # Look for "Mandarin" string
    if chinese_content: # Ensure we found Chinese section 
        found_mandarin = False
        for node in chinese_content:
            if not getattr(node, 'find_all', None): continue
            
            # Find "Mandarin" text
            mandarin_texts = node.find_all(string=lambda t: t and 'Mandarin' in t)
            for m_text in mandarin_texts:
                # exclude "Simple Mandarin", "Southwestern Mandarin" if listed separately as headers?
                # Usually standard Mandarin is just listed as "Mandarin"
                
                # Check for pinyin class nearby
                parent = m_text.parent
                
                # Case A: <li>Mandarin: <span ...>...</span></li>
                pron = parent.find_next(class_='zhpron-monospace')
                
                # Verify proximity: checks if pron is within same block
                if pron:
                    data['mandarin'] = pron.get_text(strip=True)
                    found_mandarin = True
                    break
            if found_mandarin: break

    # 3. Middle Chinese
    if chinese_content:
        found_mc = False
        # We will try to gather all MC readings since characters often have multiple.
        # But for the current structure, let's try to capture the main one and the Zhengzhang one.
        
        # We'll traverse to find "Middle Chinese" entries.
        for node in chinese_content:
            if not getattr(node, 'find_all', None): continue
            
            # Find all "Middle Chinese" labels
            mc_labels = node.find_all(string=lambda t: t and 'Middle Chinese' in t)
            
            for mc_label in mc_labels:
                li = mc_label.find_parent('li')
                if li:
                    # 1. Existing extraction (likely Baxter-Sagart)
                    pron = li.find(class_='zhpron-monospace')
                    if pron:
                        bs_text = pron.get_text(strip=True)
                        # Append if we already found some (for polyphonic characters)
                        if data['middle_chinese']['baxter_sagart']:
                            if bs_text not in data['middle_chinese']['baxter_sagart']:
                                data['middle_chinese']['baxter_sagart'] += ", " + bs_text
                        else:
                             data['middle_chinese']['baxter_sagart'] = bs_text

                    # 2. Zhengzhang Shangfang extraction
                    # The switcher is often the container of the UL/LI, or a sibling.
                    # Structure found: div.vsSwitcher > ul > li > Middle Chinese...
                    #                  div.vsSwitcher > div.vsHide > table
                    
                    switcher = li.find_parent(class_='vsSwitcher')
                    if not switcher:
                         # Fallback: sometimes it's a sibling of the UL or DL
                         # e.g. h4 > ul > li; h4 > div.vsSwitcher
                         # But based on debug.html, it's the parent.
                         switcher = li.find(class_='vsSwitcher') # Try down just in case
                         
                    if not switcher:
                        # Try finding next sibling of the UL that contains this LI
                        ul = li.find_parent('ul')
                        if ul:
                             sibling = ul.find_next_sibling()
                             if sibling and 'vsSwitcher' in sibling.get('class', []):
                                 switcher = sibling

                    if switcher:
                        # Search for Zhengzhang Shangfang row
                        # Look for 'th' or 'td' containing "Zhengzhang"
                        # The text might be split like "Zhengzhang<br>Shangfang"
                        # text=True will return "Zhengzhang" and "Shangfang" separately in get_text if stripped?
                        # We use 'Zhengzhang' search in text content.
                        rows = switcher.find_all('tr')
                        for row in rows:
                            row_text = row.get_text(separator=' ', strip=True) # Use separator to handle br
                            if 'Zhengzhang' in row_text:
                                # The value is usually in a td next to th
                                # Find the cell that contains the IPA
                                # It might be a span with class "IPAchar" or "zhpron-monospace"
                                # or just the next cell.
                                
                                # Targeted finding
                                target_cell = row.find(['td', 'th'], class_=lambda x: x != 'NavHead' if x else True)
                                # Actually we want the cell *after* the label, or the cell containing the value.
                                # The label is often in a th, value in td.
                                
                                # Better: find the IPA/value inside this row
                                ipa_span = row.find(class_=['IPAchar', 'zhpron-monospace', 'IPA'])
                                if ipa_span:
                                    zz_text = ipa_span.get_text(strip=True)
                                    if data['middle_chinese']['zhengzhang_shangfang']:
                                         if zz_text not in data['middle_chinese']['zhengzhang_shangfang']:
                                             data['middle_chinese']['zhengzhang_shangfang'] += ", " + zz_text
                                    else:
                                         data['middle_chinese']['zhengzhang_shangfang'] = zz_text
                                else:
                                    # Fallback to just getting the last cell text
                                    cells = row.find_all(['td', 'th'])
                                    if len(cells) > 1:
                                        val = cells[-1].get_text(strip=True)
                                        # Basic validation to avoid getting garbage
                                        if val and not 'Zhengzhang' in val:
                                             if data['middle_chinese']['zhengzhang_shangfang']:
                                                 if val not in data['middle_chinese']['zhengzhang_shangfang']:
                                                     data['middle_chinese']['zhengzhang_shangfang'] += ", " + val
                                             else:
                                                 data['middle_chinese']['zhengzhang_shangfang'] = val
        
        # If we found at least something, we consider it found?
        if data['middle_chinese']['baxter_sagart'] or data['middle_chinese']['zhengzhang_shangfang']:
             pass # Logic is done via accumulation

    # 4. Old Chinese (Zhengzhang Shangfang)
    # Search within the gathered Chinese content nodes
    if chinese_content:
        found_oc = False
        for node in chinese_content:
            if not getattr(node, 'descendants', None): continue
            
            # Search for specific Zhengzhang mention
            # We look for a node containing "Zhengzhang" and an IPAchar
            # Using find_all to get all 'a' tags or text is robust
            
            # Strategy: Find (Zhengzhang) link/text -> Look in parent container -> Find IPAchar
            links = node.find_all('a')
            for link in links:
                if 'Zhengzhang' in link.get('title', '') or 'Zhengzhang' in link.get_text():
                    # Found a anchor pointing to Zhengzhang
                    # Walk up to find a container (dd, li, tr)
                    parent = link.parent
                    for _ in range(6): # Go up a few levels
                        if not parent: break
                        
                        # Check specific class for pronunciation
                        # Also verify it looks like Old Chinese (starts with /* or *)
                        ipa = parent.find(class_='IPAchar')
                        if ipa:
                             text = ipa.get_text(strip=True)
                             if text.startswith('/*') or text.startswith('*'):
                                 data['old_chinese']['zhengzhang_shangfang'] = text
                                 found_oc = True
                                 break
                        
                        # Sometimes it's class='IPA' with lang='och-Latn-fonipa'
                        ipa_och = parent.find('span', lang='och-Latn-fonipa')
                        if ipa_och:
                             text = ipa_och.get_text(strip=True)
                             data['old_chinese']['zhengzhang_shangfang'] = text
                             found_oc = True
                             break
                        parent = parent.parent
                    if found_oc: break
            if found_oc: break

    # Find Japanese section
    japanese_h2 = None
    for h2 in soup.find_all('h2'):
        if 'Japanese' in h2.get_text():
            japanese_h2 = h2
            break
    
    if japanese_h2:
        start_node = japanese_h2
        if japanese_h2.parent and 'mw-heading' in japanese_h2.parent.get('class', []):
            start_node = japanese_h2.parent

        # Traverse siblings
        curr = start_node.next_sibling
        while curr:
            if curr.name == 'h2': break
            if curr.name == 'div' and 'mw-heading' in curr.get('class', []):
                 if curr.find('h2'): break

            if not getattr(curr, 'find_all', None): 
                curr = curr.next_sibling
                continue
            
            # Check for GOON
            if not data['japanese_readings']['goon']:
                goon_link = curr.find('a', string=lambda s: s and 'Go-on' in s)
                if goon_link:
                    li = goon_link.find_parent('li')
                    if li:
                         text = li.get_text(separator=' ', strip=True)
                         if 'Go-on' in text:
                             val = text.split('Go-on')[-1].strip(': ').strip()
                             data['japanese_readings']['goon'] = val

            # Check for KANON
            if not data['japanese_readings']['kanon']:
                kanon_link = curr.find('a', string=lambda s: s and ("Kan'on" in s or "Kan-on" in s))
                if kanon_link:
                    li = kanon_link.find_parent('li')
                    if li:
                         text = li.get_text(separator=' ', strip=True)
                         val = ""
                         if "Kan'on" in text:
                             val = text.split("Kan'on")[-1]
                         elif "Kan-on" in text:
                             val = text.split("Kan-on")[-1]
                         
                         data['japanese_readings']['kanon'] = val.strip(': ').strip()

            # Check for TOON
            if not data['japanese_readings']['toon']:
                toon_link = curr.find('a', string=lambda s: s and 'To-on' in s)
                if toon_link:
                    li = toon_link.find_parent('li')
                    if li:
                         text = li.get_text(separator=' ', strip=True)
                         if 'To-on' in text:
                             val = text.split('To-on')[-1].strip(': ').strip()
                             data['japanese_readings']['toon'] = val

            curr = curr.next_sibling

    return data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Crawl Wiktionary for Chinese character data.')
    parser.add_argument('character', help='The Chinese character to look up')
    args = parser.parse_args()

    result = get_character_data(args.character)
    if result:
        print(json.dumps(result, indent=4, ensure_ascii=False))

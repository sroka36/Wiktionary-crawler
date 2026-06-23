import requests
from bs4 import BeautifulSoup
import argparse
import sys
import json

def get_character_data(character):
    
    # url 지정하고, 크롤러 차단 회피.
    url = f"https://en.wiktionary.org/wiki/{character}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        # 응답 확인
        response.raise_for_status()
        with open('debug.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching page for {character}: {e}", file=sys.stderr)
        return None

    # 2. HTML 파싱
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

    # 3. 창힐 수입법 찾기
    cangjie_link = soup.select_one('span.Hani[lang="mul"]')
    if cangjie_link:
        container = cangjie_link.find_parent(['p', 'div'])
        if container:
            code = cangjie_link.find_next_sibling()
            data['cangjie'] = cangjie_link.get_text(strip=True)
            data['cangjie'] += f'({code.get_text(strip=True)})'

    # 4. Chinese 파트를 찾기.
    chinese_content = []
    chinese_h2 = None
    for h2 in soup.find_all('h2'):
        if 'Chinese' in h2.get_text():
            chinese_h2 = h2
            break
            
    
    if chinese_h2:
        # 모던 미디어 위키에서 h2는 보통 div.mw-heading에 둘러 쌓여있으니 그 div를 찾기
        start_node = chinese_h2
        if chinese_h2.parent and 'mw-heading' in chinese_h2.parent.get('class', []):
            start_node = chinese_h2.parent

        #다음 h2나 mw-heading까지를 다 긁기    
        curr = start_node.next_sibling
        while curr:
            if curr.name == 'h2': 
                break
            if curr.name == 'div' and 'mw-heading' in curr.get('class', []):
                if curr.find('h2'):
                    break
            
            chinese_content.append(curr)
            curr = curr.next_sibling

    # 5. Mandarin(MSC) 찾기
    if chinese_content:
        found_mandarin = False
        for node in chinese_content:
            if not getattr(node, 'find_all', None): continue
            
            # "Mandarin" 텍스트 찾기
            mandarin_texts = node.find_all(string=lambda t: t and 'Mandarin' in t)
            for m_text in mandarin_texts:

                # <li>에 접근
                parent = m_text.parent

                # 첫번째 zhpron-monospace 클래스 찾기 (보통 pinyin이 여기에 있음)     
                pron = parent.find_next(class_='zhpron-monospace')

                # 찾았다면 추출해서 저장하고 루프 탈출  
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

    # Japanese h2 찾기
    japanese_h2 = None
    for h2 in soup.find_all('h2'):
        if 'Japanese' in h2.get_text():
            japanese_h2 = h2
            break
    
    # h2의 부모노드 찾기
    if japanese_h2:
        start_node = japanese_h2
        if japanese_h2.parent and 'mw-heading' in japanese_h2.parent.get('class', []):
            start_node = japanese_h2.parent

        # Japanese 섹터의 형제 노드 찾기
        curr = start_node.next_sibling
        on_temp = ""
        kan_temp = ""
        to_temp = ""
        
        while curr:
            if curr.name == 'h2': break
            if curr.name == 'div' and 'mw-heading' in curr.get('class', []):
                 if curr.find('h4') and curr.find('h4').get('id') == 'Readings':
                      read_list = curr.find_next_sibling()
                      for s in read_list.find_all('span'):
                          if s.find_previous_sibling('b'):

                              # 오음 구하기
                              if s.find_previous_sibling('b').find('a').get_text() == "Go-on":
                                  if "on-yomi" in s.get('class', []):
                                      on_temp += s.get_text(separator=" ",strip=True)

                              # 한음 구하기
                              if s.find_previous_sibling('b').find('a').get_text() == "Kan-on":
                                  if "on-yomi" in s.get('class', []):
                                      kan_temp += s.get_text(separator=" ",strip=True)

                              # 당음 구하기        
                              if s.find_previous_sibling('b').find('a').get_text() == "Tō-on":
                                  if "on-yomi" in s.get('class', []):
                                      to_temp += s.get_text(separator=" ",strip=True)

                      # 없으면 None으로 처리
                      if(on_temp == ""): on_temp = None 
                      if(kan_temp == ""): kan_temp = None
                      if(to_temp == ""): to_temp = None

                      data['japanese_readings']['goon']  = on_temp
                      data['japanese_readings']['kanon'] = kan_temp
                      data['japanese_readings']['toon'] = to_temp

                 if curr.find('h2'): break

            if not getattr(curr, 'find_all', None): 
                curr = curr.next_sibling
                continue

            curr = curr.next_sibling

    return data

# 실행 시 스크립트
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Crawl Wiktionary for informations of Kanji.')
    parser.add_argument('character', help='Kanji to look up.')
    args = parser.parse_args()

    result = get_character_data(args.character)
    if result:
        print(json.dumps(result, indent=4, ensure_ascii=False))

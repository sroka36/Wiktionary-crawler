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
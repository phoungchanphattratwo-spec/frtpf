lines = open('gui.py', encoding='utf-8').readlines()

# Find the two _maxchange_random_single definitions
indices = [i for i, l in enumerate(lines) if 'def _maxchange_random_single' in l]
print(f"Found at lines: {[i+1 for i in indices]}")

# Remove the OLD stub version (first one, lines 12745-12758 approx)
# Keep the newer real implementation (second one)
if len(indices) >= 2:
    start = indices[0]  # first (old stub)
    end = indices[1]    # second (new real) - remove up to here
    print(f"Removing lines {start+1} to {end} (old stubs)")
    new_lines = lines[:start] + lines[end:]
    open('gui.py', 'w', encoding='utf-8').write(''.join(new_lines))
    print('Done')
else:
    print('Only one definition found, nothing to remove')

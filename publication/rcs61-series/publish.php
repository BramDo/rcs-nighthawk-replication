<?php
/** Publish the guarded RCS 61q bilingual series via `wp eval-file`. */

$manifest = json_decode(file_get_contents(__DIR__ . '/manifest.json'), true);
if (!is_array($manifest) || ($manifest['series'] ?? '') !== 'rcs61-20260925' || count($manifest['pages'] ?? []) !== 10) {
    throw new RuntimeException('Unexpected RCS 61q manifest');
}

$marker = 'rcs61-series-20260925';
$page_ids = [];
$published = [];
foreach ($manifest['pages'] as $page) {
    $key = $page['key'];
    $parent_key = $page['parent_key'];
    $parent_id = $parent_key ? ($page_ids[$parent_key] ?? null) : 0;
    if ($parent_id === null) {
        throw new RuntimeException("Missing parent for $key");
    }
    $matches = get_posts([
        'post_type' => 'page', 'post_status' => 'any', 'name' => $page['slug'],
        'post_parent' => $parent_id, 'numberposts' => -1,
    ]);
    if (count($matches) > 1) {
        throw new RuntimeException("Duplicate page slug under parent for $key");
    }
    $fields = [
        'post_type' => 'page', 'post_status' => 'publish',
        'post_title' => $page['title'], 'post_name' => $page['slug'],
        'post_parent' => $parent_id, 'post_content' => $page['content'],
    ];
    if ($matches) {
        $current = $matches[0];
        if (strpos($current->post_content, $marker) === false) {
            throw new RuntimeException("Existing page is not owned by this series: $key");
        }
        $fields['ID'] = $current->ID;
        $id = wp_update_post($fields, true);
        $action = 'updated';
    } else {
        $fields['post_author'] = 1;
        $id = wp_insert_post($fields, true);
        $action = 'created';
    }
    if (is_wp_error($id)) {
        throw new RuntimeException("WordPress $action failed for $key: " . $id->get_error_message());
    }
    $page_ids[$key] = (int) $id;
    $published[] = ['key' => $key, 'id' => (int) $id, 'action' => $action,
                    'url' => get_permalink($id)];
}

$menu_id = 3;
if (!wp_get_nav_menu_object($menu_id)) {
    throw new RuntimeException('Expected Menu 1 (term 3) is missing');
}
$find_item = function ($url) use ($menu_id) {
    foreach ((array) wp_get_nav_menu_items($menu_id) as $item) {
        if (untrailingslashit($item->url) === untrailingslashit($url)) {
            return $item;
        }
    }
    return null;
};
$en_root = get_permalink($page_ids['en-hub']);
$existing = $find_item($en_root);
$menu_root = wp_update_nav_menu_item($menu_id, $existing ? $existing->ID : 0, [
    'menu-item-title' => 'Nighthawk RCS 61q',
    'menu-item-url' => $en_root,
    'menu-item-status' => 'publish',
    'menu-item-type' => 'custom',
    'menu-item-parent-id' => 0,
    'menu-item-position' => $existing ? (int) $existing->menu_order : 0,
]);
if (is_wp_error($menu_root)) {
    throw new RuntimeException('Could not create the RCS menu root: ' . $menu_root->get_error_message());
}
$menu_items = [['key' => 'en-hub', 'id' => (int) $menu_root]];
for ($part = 1; $part <= 4; $part++) {
    $key = "en-$part";
    $url = get_permalink($page_ids[$key]);
    $existing = $find_item($url);
    $id = wp_update_nav_menu_item($menu_id, $existing ? $existing->ID : 0, [
        'menu-item-title' => "Part $part: " . [1 => 'The paper', 2 => 'Our IBM measurements', 3 => 'MPS and advantage', 4 => 'RCS theory and applications'][$part],
        'menu-item-url' => $url,
        'menu-item-status' => 'publish',
        'menu-item-type' => 'custom',
        'menu-item-parent-id' => (int) $menu_root,
        'menu-item-position' => $existing ? (int) $existing->menu_order : 0,
    ]);
    if (is_wp_error($id)) {
        throw new RuntimeException("Could not create menu item $key: " . $id->get_error_message());
    }
    $menu_items[] = ['key' => $key, 'id' => (int) $id];
}

clean_post_cache($page_ids['en-hub']);
wp_cache_flush();
$receipt = ['series' => $manifest['series'], 'published_at_utc' => gmdate('c'),
            'pages' => $published, 'menu' => $menu_items];
file_put_contents(__DIR__ . '/published.json', json_encode($receipt, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");
echo json_encode($receipt, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";

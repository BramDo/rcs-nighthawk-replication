<?php
/** Move the existing Nighthawk RCS menu branch immediately before Work. */

$menu_id = 3;
$root_id = 1255;
$work_id = 932;
$branch_ids = [1255, 1256, 1257, 1258, 1273];
$items = (array) wp_get_nav_menu_items($menu_id, ['post_status' => 'publish']);
usort($items, static fn($a, $b) => (int) $a->menu_order <=> (int) $b->menu_order);
$by_id = [];
foreach ($items as $item) {
    $by_id[(int) $item->ID] = $item;
}
foreach (array_merge($branch_ids, [$work_id]) as $id) {
    if (!isset($by_id[$id])) {
        throw new RuntimeException("Expected menu item $id missing");
    }
}
if ((int) $by_id[$root_id]->menu_item_parent !== 0 ||
    (int) $by_id[$work_id]->menu_item_parent !== 0 ||
    $by_id[$root_id]->title !== 'Nighthawk RCS 61q' ||
    $by_id[$work_id]->title !== 'Work') {
    throw new RuntimeException('Nighthawk or Work menu identity changed');
}
foreach (array_slice($branch_ids, 1) as $id) {
    if ((int) $by_id[$id]->menu_item_parent !== $root_id) {
        throw new RuntimeException("Nighthawk child $id has a different parent");
    }
}

$before = array_map(static fn($item) => (int) $item->ID, $items);
$branch = array_map(static fn($id) => $by_id[$id], $branch_ids);
$remaining = array_values(array_filter($items,
    static fn($item) => !in_array((int) $item->ID, $branch_ids, true)));
$work_index = null;
foreach ($remaining as $index => $item) {
    if ((int) $item->ID === $work_id) {
        $work_index = $index;
        break;
    }
}
if ($work_index === null) {
    throw new RuntimeException('Work not found in filtered menu');
}
$target = $remaining;
array_splice($target, $work_index, 0, $branch);
$target_ids = array_map(static fn($item) => (int) $item->ID, $target);
if (count($target_ids) !== count($before) || count(array_unique($target_ids)) !== count($before)) {
    throw new RuntimeException('Reorder would lose or duplicate a menu item');
}

file_put_contents(__DIR__ . '/menu_before_move.json', json_encode($before) . "\n");
$changed = 0;
foreach ($target as $index => $item) {
    $position = $index + 1;
    if ((int) $item->menu_order === $position) {
        continue;
    }
    $result = wp_update_post(['ID' => (int) $item->ID, 'menu_order' => $position], true);
    if (is_wp_error($result)) {
        throw new RuntimeException("Could not move menu item {$item->ID}: " . $result->get_error_message());
    }
    $changed++;
}
wp_cache_flush();

$after_items = (array) wp_get_nav_menu_items($menu_id, ['post_status' => 'publish']);
usort($after_items, static fn($a, $b) => (int) $a->menu_order <=> (int) $b->menu_order);
$after = array_map(static fn($item) => (int) $item->ID, $after_items);
if ($after !== $target_ids) {
    throw new RuntimeException('Live menu order differs from the planned order');
}
$non_branch_before = array_values(array_filter($before,
    static fn($id) => !in_array($id, $branch_ids, true)));
$non_branch_after = array_values(array_filter($after,
    static fn($id) => !in_array($id, $branch_ids, true)));
if ($non_branch_before !== $non_branch_after) {
    throw new RuntimeException('Unrelated menu items changed relative order');
}
$root_index = array_search($root_id, $after, true);
if (array_slice($after, $root_index, count($branch_ids) + 1) !== array_merge($branch_ids, [$work_id])) {
    throw new RuntimeException('Nighthawk branch is not immediately before Work');
}
$report = ['menu_id' => $menu_id, 'moved_branch' => $branch_ids,
           'work_id' => $work_id, 'new_root_position' => $root_index + 1,
           'new_work_position' => $root_index + count($branch_ids) + 1,
           'items_updated' => $changed, 'unrelated_relative_order_preserved' => true];
file_put_contents(__DIR__ . '/menu_move_report.json', json_encode($report, JSON_PRETTY_PRINT) . "\n");
echo json_encode($report, JSON_PRETTY_PRINT) . "\n";

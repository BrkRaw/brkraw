"""Public API names used in the 0.6.0 docs (b1 bundle B6)."""


def test_layout_is_public():
    from brkraw.api import layout

    assert callable(layout.render_layout)
    assert callable(layout.load_layout_info_parts)
    assert callable(layout.render_slicepack_suffixes)


def test_context_map_and_pruner_are_public():
    from brkraw.api import context_map, pruner

    for name in ("load_context_map", "validate_context_map", "find_context_map", "plan_scan"):
        assert callable(getattr(context_map, name))
    for name in ("prune_dataset_to_zip", "prune_dataset_to_zip_from_spec", "select_files", "resolve_prune_spec"):
        assert callable(getattr(pruner, name))

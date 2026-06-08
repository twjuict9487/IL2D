param(
    [string]$Path = "System_IL2D/core/Pre_coded_data/game_data/missions.json",
    [string]$OutputPath = ""
)

function Clean-Text($value) {
    if ($null -eq $value) { return "" }
    return [string]$value
}

function Add-If([hashtable]$table, [string]$key, $value) {
    if ($null -eq $value) { return }
    if ($value -is [string]) {
        if ([string]::IsNullOrWhiteSpace($value)) { return }
        $table[$key] = $value
        return
    }
    if ($value -is [System.Collections.IEnumerable] -and -not ($value -is [string])) {
        $arr = @($value)
        if ($arr.Count -eq 0) { return }
        $table[$key] = $value
        return
    }
    $table[$key] = $value
}

$data = Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json

foreach ($mission in @($data.missions)) {
    $objectives = @()
    foreach ($obj in @($mission.objectives)) {
        if ($null -eq $obj) { continue }
        $clean = [ordered]@{}
        foreach ($prop in $obj.PSObject.Properties) {
            if ($prop.Name -in @("progress", "done", "source", "mode", "status")) { continue }
            $clean[$prop.Name] = $prop.Value
        }
        $objectives += [pscustomobject]$clean
    }
    $mission.objectives = @($objectives)

    $type = Clean-Text($mission.type)
    if (-not $type) { $type = Clean-Text($mission.mission_type) }
    if (-not $type -and $mission.objectives.Count -gt 0) {
        $type = Clean-Text($mission.objectives[0].type)
    }
    if ($type) {
        $mission | Add-Member -NotePropertyName type -NotePropertyValue $type -Force
    }

    $params = [ordered]@{}
    $primary = if ($mission.objectives.Count -gt 0) { $mission.objectives[0] } else { $null }
    if ($null -ne $primary) {
        if ($null -ne $primary.target) {
            Add-If $params "amount" ([int]$primary.target)
        }
        switch (Clean-Text($type)) {
            "complete_missions" {
                if (-not $params.Contains("amount")) { $params["amount"] = 1 }
                if ($primary.PSObject.Properties.Name -contains "high_risk") {
                    $params["high_risk"] = [bool]$primary.high_risk
                }
            }
            "high_risk_mission" {
                Add-If $params "base_type" (Clean-Text($primary.base_type))
                Add-If $params "mob_id" (Clean-Text($primary.mob_id))
                if (-not $params["mob_id"]) { Add-If $params "mob_id" (Clean-Text($primary.mob)) }
                Add-If $params "target_buff" (Clean-Text($primary.target_buff))
                if ($primary.spawn_rule) { $params["spawn_rule"] = $primary.spawn_rule }
            }
            "kill_enemy" {
                Add-If $params "mob_id" (Clean-Text($primary.mob_id))
                if (-not $params["mob_id"]) { Add-If $params "mob_id" (Clean-Text($primary.mob)) }
                Add-If $params "map" (Clean-Text($primary.map))
                Add-If $params "target_buff" (Clean-Text($primary.target_buff))
                if ($primary.spawn_rule) { $params["spawn_rule"] = $primary.spawn_rule }
            }
            "kill_elite_enemy" {
                Add-If $params "mob_id" (Clean-Text($primary.mob_id))
                if (-not $params["mob_id"]) { Add-If $params "mob_id" (Clean-Text($primary.mob)) }
                Add-If $params "map" (Clean-Text($primary.map))
                Add-If $params "target_buff" (Clean-Text($primary.target_buff))
                if ($primary.spawn_rule) { $params["spawn_rule"] = $primary.spawn_rule }
                $params["elite_only"] = $true
            }
            "collect_item" {
                Add-If $params "item_id" (Clean-Text($primary.item_id))
                if (-not $params["item_id"]) { Add-If $params "item_id" (Clean-Text($primary.key_label)) }
                Add-If $params "source_filter" $primary.source_filter
                if ($primary.rare_drop_rules) { $params["rare_drop_rules"] = $primary.rare_drop_rules }
            }
            "collect_data" {
                Add-If $params "map_pool" $primary.map_pool
                Add-If $params "target_tiles" $primary.target_tiles
                Add-If $params "outline_color" (Clean-Text($primary.outline_color))
                Add-If $params "interaction_id" (Clean-Text($primary.interaction_id))
                if (-not $params["interaction_id"]) { Add-If $params "interaction_id" (Clean-Text($primary.target_id)) }
            }
            "upload_data" {
                Add-If $params "terminal_id" (Clean-Text($primary.terminal_id))
                if (-not $params["terminal_id"]) { Add-If $params "terminal_id" (Clean-Text($primary.target_id)) }
                Add-If $params "required_flag" (Clean-Text($primary.required_flag))
                if (-not $params["required_flag"]) { Add-If $params "required_flag" (Clean-Text($primary.set_flag)) }
                Add-If $params "duration_range" $primary.duration_range
            }
            "talk_to_npc" {
                Add-If $params "npc_id" (Clean-Text($primary.npc_id))
                if (-not $params["npc_id"]) { Add-If $params "npc_id" (Clean-Text($primary.target_id)) }
                Add-If $params "mission_dialogue_node" (Clean-Text($primary.mission_dialogue_node))
                Add-If $params "required_flag" (Clean-Text($primary.required_flag))
            }
        }
    }

    $mission | Add-Member -NotePropertyName params -NotePropertyValue ([pscustomobject]$params) -Force
    if (-not ($mission.PSObject.Properties.Name -contains "description") -and $mission.description_lines) {
        $mission | Add-Member -NotePropertyName description -NotePropertyValue $mission.description_lines -Force
    }
}

$targetPath = if ([string]::IsNullOrWhiteSpace($OutputPath)) { $Path } else { $OutputPath }
$data | ConvertTo-Json -Depth 100 | Set-Content -Path $targetPath -Encoding UTF8

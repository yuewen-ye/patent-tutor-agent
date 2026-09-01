$ErrorActionPreference = 'Continue'
$base = "D:\workspace-agent\patnet-turor-agent\backend\tests\evaluation\results\record"
$groups = @("multi","nodebate","norag","norerank","singlemodel")
$profiles = @("H","M","N")
$out = @()
foreach ($g in $groups) {
  foreach ($p in $profiles) {
    $pf = Join-Path $base "$g\profile_indicator_gemini-3.7-flash_$p.json"
    if (Test-Path $pf) {
      try {
        $pj = Get-Content $pf -Raw -Encoding UTF8 | ConvertFrom-Json
        $cr = $pj.cross_round
        $out += [pscustomobject]@{level="profile"; group=$g; profile=$p; scr=$cr.self_consistency_rate; tfp=$cr.total_fact_points; contra=$cr.contradicted}
      } catch {
        $out += [pscustomobject]@{level="profile_err"; group=$g; profile=$p; note=$_.Exception.Message}
      }
    }
    for ($r=1; $r -le 5; $r++) {
      $rr = "{0:D2}" -f $r
      $f = Join-Path $base "$g\round_indicator_gemini-3.7-flash_${p}_$rr.json"
      if (-not (Test-Path $f)) { $out += [pscustomobject]@{level="missing"; group=$g; profile=$p; round=$r}; continue }
      try {
        $j = Get-Content $f -Raw -Encoding UTF8 | ConvertFrom-Json
        $s = $j.overall.overall_evaluation.scores
        $out += [pscustomobject]@{
          level="round"; group=$g; profile=$p; round=$r;
          ctx=$s.context_correctness.score; corr=$s.correctness.score; hall=$s.hallucination.score;
          help=$s.helpfulness.score; rel=$s.relevance.score; diffit=$s.difficulty_fit.score;
          oscore=$j.overall.overall_evaluation.overall_score.score;
          st_total=$j.statement.m1_hallucination_rate.total;
          st_inc=$j.statement.m1_hallucination_rate.incorrect;
          st_rate=$j.statement.m1_hallucination_rate.verdict_based_rate;
          src_ws=$j.statement.m9_source_verifiable_rate.total_with_source;
          src_fv=$j.statement.m9_source_verifiable_rate.fully_verified;
          src_rel=$j.statement.m9_source_verifiable_rate.content_relevant;
          src_rate=$j.statement.m9_source_verifiable_rate.verdict_based_rate;
          ret_t=$j.retrieval.total_chunks; ret_acc=$j.retrieval.accurate; ret_acr=$j.retrieval.accurate_rate;
          ret_cmp=$j.retrieval.complete; ret_cmr=$j.retrieval.complete_rate;
          cov_s=$j.coverage.section_coverage.score; cov_w=$j.coverage.weakness_coverage.score;
          cov_c=$j.coverage.confusion_coverage.score; cov_a=$j.coverage.overall_coverage_score.score;
          pii=$j.pii.pii_leak_count
        }
      } catch {
        $out += [pscustomobject]@{level="round_err"; group=$g; profile=$p; round=$r; note=$_.Exception.Message}
      }
    }
    $sf = Join-Path $base "$g\system_indicator_gemini-3.7-flash.json"
    if (Test-Path $sf) {
      try {
        $sj = Get-Content $sf -Raw -Encoding UTF8 | ConvertFrom-Json
        $adv = $sj.m6_adversarial
        $bnd = $sj.m6_boundary
        $bndTotal = @($bnd.evaluations).Count
        $bndAppr = @($bnd.evaluations | Where-Object { $_.appropriate -eq $true }).Count
        $advTotal = @($adv.evaluations).Count
        $advPass = @($adv.evaluations | Where-Object { $_.passed -eq $true }).Count
        $out += [pscustomobject]@{level="system"; group=$g;
          adv_t=$adv.total_questions; adv_p=$adv.passed; adv_r=$adv.pass_rate;
          adv_eval_t=$advTotal; adv_eval_p=$advPass;
          bnd_t=$bndTotal; bnd_p=$bndAppr; bnd_r=[math]::Round(100.0*$bndAppr/[math]::Max(1,$bndTotal),1);
          adv_ts=$adv.metadata.timestamp}
      } catch {
        $out += [pscustomobject]@{level="system_err"; group=$g; note=$_.Exception.Message}
      }
    }
  }
}
$outPath = "D:\workspace-agent\patnet-turor-agent\_metrics_out.json"
$out | ConvertTo-Json -Depth 4 | Out-File -FilePath $outPath -Encoding UTF8
Write-Output ("DONE " + $out.Count)

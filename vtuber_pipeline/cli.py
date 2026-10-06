"""Click-based CLI for VTuber Pipeline."""

import click


@click.group()
def cli():
    """VTuber 상업용 파이프라인 CLI"""
    pass


@cli.command()
@click.option('--image', required=True, type=click.Path(exists=True), help='입력 이미지 경로')
@click.option('--output', required=True, type=click.Path(), help='출력 디렉터리')
@click.option('--profile', default='commercial', help='라이선스 프로파일 (commercial)')
@click.option('--commercial-usage', type=click.Choice(['personalNonProfit', 'personalProfit', 'corporation']), default='corporation', help='상업용 사용 권한 (기본값: corporation)')
def avatar(image, output, profile, commercial_usage):
    """이미지에서 VTuber 아바타를 생성합니다."""
    from vtuber_pipeline.avatar.build import build_avatar
    import pathlib
    
    click.echo(f'아바타 빌드 시작: {image}')
    click.echo(f'출력 디렉터리: {output}')
    click.echo(f'프로파일: {profile}')
    click.echo(f'상업용 권한: {commercial_usage}')
    
    result = build_avatar(image, output, {"profile": profile, "commercial_usage": commercial_usage})
    
    # Report stage results
    stages = result.get("stages", {})
    stage_names = [
        ("input_gate", "입력 검증"),
        ("face_landmarks", "얼굴 랜드마크"),
        ("reference_reconstruction", "3D 재구성"),
        ("reference_analysis", "메시 분석"),
        ("template_fitting", "템플릿 피팅"),
        ("deformation_transfer", "변형 전송"),
        ("texture_transfer", "텍스처 전송"),
        ("hair", "헤어 추출"),
        ("clothing", "의상 추출"),
        ("rig", "리깅"),
        ("expressions", "표정 생성"),
        ("gaze", "시선 설정"),
        ("springbone", "스프링본"),
        ("materials", "머티리얼"),
        ("vrm_export", "VRM 내보내기"),
        ("validator", "검증")
    ]
    
    for stage_key, stage_name in stage_names:
        stage_result = stages.get(stage_key, {})
        status = stage_result.get("status", "unknown")
        if status == "complete":
            click.echo(f'  ✓ {stage_name}')
        elif status == "stub":
            click.echo(f'  ○ {stage_name} (stub)')
        elif status == "error":
            error = stage_result.get("error", "unknown error")
            click.echo(f'  ✗ {stage_name}: {error}')
        else:
            click.echo(f'  · {stage_name}: {status}')
    
    # Final result
    if result.get("status") == "complete":
        vrm_path = pathlib.Path(output) / "avatar.vrm"
        click.echo(f'\n완료! VRM 파일: {vrm_path}')
        validation = stages.get("validator", {})
        if validation.get("passed"):
            click.echo('VRM 검증: 통과')
        else:
            click.echo('VRM 검증: 경고 (일부 항목 미달)')
    else:
        click.echo(f'\n빌드 실패: {result.get("failed_stages", [])}')


@cli.command()
@click.option('--images', required=True, multiple=True, type=click.Path(exists=True), help='입력 이미지 경로들')
@click.option('--output', required=True, type=click.Path(), help='출력 디렉터리')
def accessory(images, output):
    """이미지들에서 VTuber 액세서리를 배치 생성합니다."""
    from vtuber_pipeline.accessory.reconstruction import reconstruct_accessories
    from vtuber_pipeline.accessory.attachment import generate_attachment_config
    import pathlib
    click.echo(f'[1/2] {len(images)}개 액세서리 3D 재구성 중...')
    results = reconstruct_accessories(list(images), output)
    meshes = [r['mesh'] for r in results if r['mesh']]
    click.echo(f'[2/2] attachment.json 생성 중...')
    config_path = str(pathlib.Path(output) / 'attachment.json')
    generate_attachment_config(meshes, config_path)
    click.echo(f'완료: {config_path}')


if __name__ == '__main__':
    cli()

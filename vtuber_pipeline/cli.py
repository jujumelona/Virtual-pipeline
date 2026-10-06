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
def avatar(image, output, profile):
    """이미지에서 VTuber 아바타를 생성합니다."""
    from vtuber_pipeline.avatar.reconstruction import reconstruct_avatar
    click.echo(f'[1/4] 3D 재구성 중: {image}')
    mesh = reconstruct_avatar(image, output, profile)
    click.echo(f'[1/4] 완료: {mesh}')
    click.echo('[2/4] 템플릿 피팅 (미구현 — 향후 릴리즈 예정)')
    click.echo('[3/4] 리깅 (미구현 — 향후 릴리즈 예정)')
    click.echo('[4/4] VRM 내보내기 (미구현 — 향후 릴리즈 예정)')


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

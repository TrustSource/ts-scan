import click
from click.testing import CliRunner

from ts_scan.cli import inout_default_options


@click.command()
@inout_default_options(_in=False, _out=True, _fmt=False)
def output_command(output_path):
    click.echo(output_path)


def test_output_option_rejects_directory(tmp_path):
    result = CliRunner().invoke(output_command, ['-o', str(tmp_path)])

    assert result.exit_code == 2
    assert 'is a directory' in result.output


def test_output_option_accepts_file_path(tmp_path):
    output_path = tmp_path / 'scan.json'

    result = CliRunner().invoke(output_command, ['-o', str(output_path)])

    assert result.exit_code == 0
    assert str(output_path) in result.output

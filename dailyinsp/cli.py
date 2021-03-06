import click
import pypandoc
from pathlib import Path
from zipfile import ZipFile
from datetime import datetime, timedelta

from .cms.gembot import GemBot
from .parser.htmlparser import HtmlData

echo = click.echo


def check_day(input_day, today, days):
    '''Recursively find the next date from today that matches the input day date integer.'''
    checkday = today + timedelta(days=days)
    if input_day == checkday.day:
        return checkday
    else:
        return check_day(input_day, today, days + 1)


def get_date(date):
    '''Get live date from integer based on today's date.'''
    today = datetime.today()
    in_day = date.strip().split(" ")
    in_date = check_day(input_day=int(in_day[1]), today=today, days=1)
    # return date when input text matches the next corresponding date day
    if int(in_day[1]) == in_date.day:
        return in_date
    else:
        live_date = in_date.strftime("%d-%m-%Y")
        print(f"{date} failed to match: {live_date}")
        return False


def extract_zip(zip_file):
    '''Unzip input zip file to a temporary folder and output files within temp.'''
    path = Path(zip_file).parent
    tmp = Path(path / 'tmp')
    if not [f for f in tmp.glob('*')]:
        with ZipFile(zip_file, 'r') as zf:
            zf.extractall(tmp)
    return tmp


def convert_docx(file):
    '''Convert the unzipped docx from input zip file argument.'''
    try:
        content = pypandoc.convert_file(
            str(file), "html5")  # extra_args=extra_args
        return content
    except Exception as e:
        echo("\tproblem converting file:", file)
        raise e  # log instead of raise


def html_data(html):
    '''use the htmlparser module to extract data from converted docx object.'''
    htd = HtmlData(html)
    htd.process_text()
    html_data = htd.process_ids()
    return html_data


def run_cleanup(temp):
    '''A cleanup function to remove the temp extraction directory.'''
    for f in temp.glob('*'):
        f.unlink()
        echo('\tRemoved files: ' + click.style(f, fg='cyan'))
    temp.rmdir()
    echo('\tRemoved temp dir: ' + click.style(temp, fg='cyan'))


def run_process(zipfile, cms, access, guest):
    '''The process for each zip file, so can be iterated over for all files in directory.'''
    # unzip file to temp folder
    temp_folder = extract_zip(Path(zipfile))
    docx = convert_docx(next(temp_folder.glob('*.docx')))
    # dictionary of values
    data = html_data(docx)
    # add windows path as string
    try:
        data['img_path'] = next(temp_folder.glob('*.jpg')).__str__()
    except StopIteration as e:
        data['img_path'] = next(temp_folder.glob('*.png')).__str__()

    raw_date = data["insp_day"].title()
    date = get_date(raw_date)
    if date:
        data.update(
            {"live_day": date.day, "live_month": date.month, "live_year": date.year}
        )
        # returns True if saved, else False
        insp = cms.inspiration_details(data)
        if insp:
            resolved_url = cms.get_url()
            cms.campaign_details(data)
            echo(click.style("\tFinished correctly", fg="green"))
            input("Finished?")
            echo('Resolved url: ' + click.style(resolved_url,
                                                fg="yellow"))
        else:
            echo("Inspiration not saved")
            pass
        run_cleanup(temp_folder)
    else:
        echo("\tNo live date: " + click.style('Exit', fg="red"))


@click.command()
@click.option(
    "-i",
    "-f",
    "-z",
    "-zf",
    "--infile",
    required=True,
    help="The input zip file directory.",
)
@click.option(
    "-a",
    "--access",
    default=False,
    show_default=True,
    type=bool,
    help="Flag True if an open access link is required.",
)
@click.option(
    "-g",
    "--guest",
    default=False,
    show_default=True,
    type=bool,
    help="Flag True if the article was guest edited to tick cms tickbox.",
)
def main(infile, access, guest):
    echo("\tUnzipping: " + click.style(infile, fg="cyan"))
    echo("\tOpen access: " + click.style(access, fg="green")
         ) if access == True else echo(
        "\tOpen access: " + click.style(access, fg="red"))
    echo("\tGuest edited: " + click.style(guest, fg="green")
         ) if guest == True else echo(
        "\tGuest edited: " + click.style(guest, fg="red"))

    # login to cms once
    cms = GemBot(open_access=access,
                 guest_edited=guest)
    try:
        cms.login()
        infile = Path(infile)
        if infile.is_dir():
            for z in infile.glob('*.zip'):
                print(z)
                run_process(z, cms, access, guest)
        elif infile.is_file():
            run_process(infile, cms, access, guest)
        else:
            echo("Input must be a folder or a zip file.")
    except Exception as e:
        echo(click.style("\tError while running cms", fg="red"))
        raise e
    finally:
        echo("Quit selenium.")
        cms.bot.quit()

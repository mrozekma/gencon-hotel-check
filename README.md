![](/../imgs/demo.png)

This script polls the Gencon housing website looking for hotel rooms near the ICC, and alerts you in a variety of ways when available rooms are found. It requires a relatively modern version of [Python](https://www.python.org/) 2 (2.7.9+).

## Usage

To fetch and run the script, open a terminal (Linux, Mac) / command prompt (Windows) and run:

```sh
git clone https://github.com/mrozekma/gencon-hotel-check.git
cd gencon-hotel-check
python gencon-hotel-check.py
```

If you don't have git, you can open the [raw file](https://raw.githubusercontent.com/mrozekma/gencon-hotel-check/master/gencon-hotel-check.py) on Github and save it.

`gencon-hotel-check.py --help` outputs the complete list of arguments, but these are the most important:

* `--key` is the only mandatory argument, specifying your individual Passkey ID number. You can find this via the [Gencon Housing](https://www.gencon.com/housing) page. Click the "Go to Housing Portal" button and you will end up on a page with a URL of the form `https://aws.passkey.com/reg/XXXXXXXX-XXXX/null/null/1/0/null`. Pass `XXXXXXXX-XXXX` as the key argument to the script.
* `--checkin` and `--checkout` specify the date range you need. The default is the days of the convention, Thursday through Sunday. Since Wednesday through Sunday is also very common, you can use `--wednesday` as a shorthand.

**NOTE**: I recommend that after setting things up the first time, including the miscellaneous alerts, you try one run including the `--test` flag. This will trigger all the alerts you've requested with some test data, to make sure they're working correctly. I make no guarantees that they'll work when a real hotel room is found, but checking that they're right ahead of time can't hurt. Speaking of which:

## Alerts

Once a hotel is found, the script needs to alert you in some way. It will output the matching hotel(s) with exclamation points next to them, but unless you're looking at the terminal at the time that probably won't help. You can specify any combination of the following options, multiple times each if necessary (e.g. to e-mail multiple people).

### Show popup

![](/../imgs/alert-popup.png)

`gencon-hotel-check.py --popup`

Popup a dialog box. On Windows this will use the win32 api if possible (via the [pypiwin32 package](https://pypi.python.org/pypi/pypiwin32/)). If not, or on other platforms, it uses Tkinter, which is typically built into Python.

### Run command

`gencon-hotel-check.py --cmd CMD`

Run the specified command, passing each hotel as a separate argument. This is probably most useful on Linux. For example, passing the path to this script will result in a libnotify popup:

```sh
#!/bin/bash
lines="$1"
shift
for i in "$@"; do
	lines="$lines\n$i"
done
notify-send -u critical "Gencon Hotel Alert" "$lines"
```

![](/../imgs/alert-libnotify.png)

### Open browser

`gencon-hotel-check.py --browser`

Open the housing site in the system's default browser. There's no simple way to open the search results directly, so it will send you to the first page of the housing search wizard.

### Send e-mail

`gencon-hotel-check.py --email SMTP_HOST FROM_ADDRESS TO_ADDRESS`

Send an e-mail that lists the found hotels and includes a link to the housing site. Most SMTP servers are authenticated, so you need to give a from address that has permission to send via specified SMTP server, and give the corresponding password when running the script. If you have an unauthenticated SMTP server available, you can use that instead and leave the password blank when the script asks. The script has been tested with Gmail, so I can confirm that if nothing else, it works there (host is `smtp.gmail.com`).

### SMS

SMS messaging is not directly supported, as it generally requires access to a paid API. However, most carriers provide a [gateway](https://en.wikipedia.org/wiki/SMS_gateway#Email_clients) that can be used to send SMS messages via e-mail. This is the main reason the e-mail alert option provides a distinct "to" address -- it's expected that you'll be sending the e-mail to yourself (i.e. to the "from" address), but you can also send it to your phone via an SMS gateway.

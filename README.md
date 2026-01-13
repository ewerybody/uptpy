# **uptpy** - compact Python FTP uploader

When building with static site generators I'd like to push and see the result asap!
How to do that? Usually uploaders shove all files that end up in the `public` directory and have no idea what was already up-to-date and what was renamed and can be deleted now.
To mitigate the deletion problem you might push to a new directory and switch the online one with the new in an instant. But that still has the Uploading-all problem.

So we need to know what actually has to be updated! For that we'll maintain a manifest file containing filenames and hashes for each
target directory. If such file is not yet present all the files are initially pushed.
Then we always just check against a local manifest and sync anything that's off.

Pros:
* one single .py file
* no extra Python packages
* checks are done super quickly
* actual update uploads as compact as possible
* deletions handled as well (of files once uploaded via `uptpy`)
* any other remote dirs and files ignored by default

Cons:
* initially ALL files need to be uploaded (we "could" instead download first
  and update if necessary. TBD)
* If a file is removed remotely `uptpy` wouldn't notice. (We could do a post-
  check to fix any missing files. (TBD [#2](https://github.com/ewerybody/uptpy/issues/2))
* we need to have this remote manifest file (which could potentially be found
  on the server and reveal files and hashes) (we could however obfuscate it at
  least a little.)
* nothing concurrent yet (we could try downloading the manifest while scanning locally) (currently it all just took split seconds so there was no pressure yet)

# How to use
`TBD`
## the fastest method

* get a copy of `uptpy.py`
* run it `python uptpy.py {HOSTURL} {USER} {PASSWD} {LOCAL_PATH} {REMOTE_PATH}`

For example with HUGO:
```
...
jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v2

      - name: Hugo setup
        uses: peaceiris/actions-hugo@v2.6.0

      - name: FTP Deploy
        run: python uptpy.py example-url.com ${{ secrets.USER }} ${{ secrets.PASSW }} public remote_subdir
```
Of course that'd require:
* `uptpy.py` to be in the root
* `example-url.com` replaced with the host adress for the FTP
* `secrets.USER` to point to the user name in your projects secrets
* `secrets.PASSW` to point to the password to be used with this user
* `public` would be the path to the output folder by HUGO
* `remote_subdir` any folder on the FTP to put things under.


# history

I built a HUGO site for friends and have them host the code on Github. They could make changes on the `.md` files, commit and Voilà: The page was updated ... soon ... ish.
Initially I set up some Github Action that used a suggested FTP project. The action was building with HUGO, checking out the FTP project from github, have it compile itself somehow and use it to push the public contents. All in all this took **about 2 minutes**!! Having some XP with Python, FTP, manifest files and hashes I hacked together a first draft and wired it up in Github actions. Slashing down the update time to about 10 seconds!

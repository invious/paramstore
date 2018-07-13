# paramstore
Finds all string defined lambda constants in the form `WEBSITE_URL: https://google.com` and adds them to the parameter store, creates the params in the template, and links those constants to the parameters

usage: `python param_store.py --app seatgeek --profiles 1ticketdev,dti1ticketprod`

It adds all of the params to param store in the specified profiles.

It edits your `template.yaml` and replaces your string constants with `!Ref`s to params defined at the top of the file

![](https://i.imgur.com/mTKzHsz.png)

![](https://i.imgur.com/0cqx8Yl.png)

and modifies your deploy script to point to the newly created parameters:

![](https://i.imgur.com/80ubcnD.png)

(Notice the duplicates, they must be removed by hand for now)

You can add it to your `/usr/local/bin`:

Make the file executable with

```
chmod +x param_store.py
cp param_store.py /usr/local/bin/param_store
```

run in any directory `param_store --app seatgeek --profiles 1ticketdev,dti1ticketprod`
# paramstore

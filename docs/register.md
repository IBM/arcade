<form id="signup-form" action="/signup" method="POST">
    <input type="email" name="email" placeholder="Enter Email">
    <input type="password" name="password" placeholder="Enter Password">
    <button type="submit" role="button">Submit</button>
</form>

<script>
form.addEventListener('submit', (event) => {

    // disable default action
    event.preventDefault();
    
    // make post request
    fetch('https://arcade.spacetech-ibm.com/auth/register', {
        method: 'POST',
        body: new FormData(form),
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    })
    .then(res => res.text())
    .then(html => console.log(html))
    .catch(err => console.error(err));
});
</script>

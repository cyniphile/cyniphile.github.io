https://www.dataquest.io/blog/how-to-setup-a-data-science-blog/

To write a new post:
    - write it, in a jupyter notebook
    - move the `.ipynb` file to the `content/` directory
    - also, make an empty file with the same name as the notebook, but with the
        extension `.nbdata`
        - in _this_ file, add meta data in the following form:

            Title: First Post
            Slug: first-post
            Date: 2016-06-08 20:00
            Category: posts
            Tags: python firsts
            author: Vik Paruchuri
            Summary: My first post, read it to find out.
    - run `pelican content`



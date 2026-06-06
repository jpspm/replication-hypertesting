public class simpleListSize {

    public static int listSizeLeak(int h) {
        int r = 0;
        int ret;
        if (h < 10) {
            r = h;
        }
        ret = r;
        return ret;
    }

}
